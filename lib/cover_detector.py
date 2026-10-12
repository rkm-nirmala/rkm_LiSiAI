from io import BytesIO
from statistics import pstdev

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError


MAX_FRAME_PIXELS = 320 * 240


def _corner_angle(first, vertex, last):
    first_vector = np.array(first, dtype=np.float32) - vertex
    last_vector = np.array(last, dtype=np.float32) - vertex
    denominator = np.linalg.norm(first_vector) * np.linalg.norm(last_vector)
    if denominator == 0:
        return 0
    cosine = np.clip(np.dot(first_vector, last_vector) / denominator, -1, 1)
    return float(np.degrees(np.arccos(cosine)))


def _find_cover_corners(gray):
    height, width = gray.shape
    frame_area = width * height
    edges = cv2.Canny(gray, 45, 135)
    contours, _hierarchy = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []

    for contour in contours:
        perimeter = cv2.arcLength(contour, True)
        if perimeter == 0:
            continue
        polygon = cv2.approxPolyDP(contour, 0.025 * perimeter, True)
        if len(polygon) != 4 or not cv2.isContourConvex(polygon):
            continue

        corners = polygon.reshape(4, 2).astype(np.float32)
        area = abs(cv2.contourArea(corners))
        if not frame_area * 0.18 <= area <= frame_area * 0.92:
            continue

        angles = [
            _corner_angle(corners[(index - 1) % 4], corners[index], corners[(index + 1) % 4])
            for index in range(4)
        ]
        if min(angles) < 55 or max(angles) > 125:
            continue

        sides = [
            float(np.linalg.norm(corners[(index + 1) % 4] - corners[index]))
            for index in range(4)
        ]
        width_estimate = (sides[0] + sides[2]) / 2
        height_estimate = (sides[1] + sides[3]) / 2
        aspect_ratio = width_estimate / height_estimate if height_estimate else 0
        if not 0.4 <= aspect_ratio <= 1.4:
            continue

        candidates.append((area, corners))

    if not candidates:
        return None

    _area, corners = max(candidates, key=lambda candidate: candidate[0])
    ordered = np.zeros((4, 2), dtype=np.float32)
    sums = corners.sum(axis=1)
    differences = np.diff(corners, axis=1).reshape(-1)
    ordered[0] = corners[np.argmin(sums)]
    ordered[2] = corners[np.argmax(sums)]
    ordered[1] = corners[np.argmin(differences)]
    ordered[3] = corners[np.argmax(differences)]
    return ordered


def _rectify_cover(gray, corners):
    top_left, top_right, bottom_right, bottom_left = corners
    cover_width = max(
        np.linalg.norm(bottom_right - bottom_left),
        np.linalg.norm(top_right - top_left),
    )
    cover_height = max(
        np.linalg.norm(top_right - bottom_right),
        np.linalg.norm(top_left - bottom_left),
    )
    target_width = max(1, round(cover_width))
    target_height = max(1, round(cover_height))
    destination = np.array(
        [
            [0, 0],
            [target_width - 1, 0],
            [target_width - 1, target_height - 1],
            [0, target_height - 1],
        ],
        dtype=np.float32,
    )
    transform = cv2.getPerspectiveTransform(corners, destination)
    return cv2.warpPerspective(gray, transform, (target_width, target_height))


def _overlap_ratio(first, second):
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[0] + first[2], second[0] + second[2])
    bottom = min(first[1] + first[3], second[1] + second[3])
    intersection = max(0, right - left) * max(0, bottom - top)
    smaller_area = min(first[2] * first[3], second[2] * second[3])
    return intersection / smaller_area if smaller_area else 0


def _text_character_boxes(gray):
    height, width = gray.shape
    max_character_area = max(100, int(width * height * 0.02))
    detector = cv2.MSER_create(5, 4, max_character_area)
    _regions, boxes = detector.detectRegions(gray)

    candidates = []
    for x, y, box_width, box_height in boxes:
        area = box_width * box_height
        aspect_ratio = box_width / box_height if box_height else 0
        if (
            3 <= box_width <= width * 0.12
            and 5 <= box_height <= height * 0.2
            and 0.08 <= aspect_ratio <= 1.5
            and 12 <= area <= max_character_area
        ):
            candidates.append((int(x), int(y), int(box_width), int(box_height)))

    unique_boxes = []
    for box in sorted(candidates, key=lambda item: item[2] * item[3]):
        if not any(_overlap_ratio(box, existing) > 0.75 for existing in unique_boxes):
            unique_boxes.append(box)
    return unique_boxes


def _text_line_count(boxes):
    lines = []
    for box in sorted(boxes, key=lambda item: item[1] + item[3] / 2):
        center_y = box[1] + box[3] / 2
        matching_line = next(
            (
                line
                for line in lines
                if abs(center_y - line["center_y"]) <= max(box[3], line["height"]) * 0.65
            ),
            None,
        )
        if matching_line is None:
            lines.append(
                {
                    "boxes": [box],
                    "center_y": center_y,
                    "height": box[3],
                }
            )
        else:
            matching_line["boxes"].append(box)
            matching_line["center_y"] = sum(
                item[1] + item[3] / 2 for item in matching_line["boxes"]
            ) / len(matching_line["boxes"])
            matching_line["height"] = max(matching_line["height"], box[3])

    text_lines = 0
    for line in lines:
        ordered = sorted(line["boxes"], key=lambda item: item[0])
        groups = []
        for box in ordered:
            if not groups:
                groups.append([box])
                continue

            previous = groups[-1][-1]
            gap = box[0] - (previous[0] + previous[2])
            if gap <= max(box[3], previous[3]) * 2.5:
                groups[-1].append(box)
            else:
                groups.append([box])

        for group in groups:
            if len(group) < 3:
                continue

            widths = pstdev(box[2] for box in group)
            heights = pstdev(box[3] for box in group)
            gaps = pstdev(
                group[index][0] - (group[index - 1][0] + group[index - 1][2])
                for index in range(1, len(group))
            ) if len(group) >= 4 else 0
            if widths >= 1.25 or heights >= 1.5 or gaps >= 1.5:
                text_lines += 1
    return text_lines


def detect_text_regions(image_bytes):
    try:
        with Image.open(BytesIO(image_bytes)) as source:
            if source.width * source.height > MAX_FRAME_PIXELS:
                raise ValueError("Ukuran frame melebihi batas deteksi 320 × 240 piksel.")
    except UnidentifiedImageError as error:
        raise ValueError("Frame kamera tidak dapat dibaca sebagai gambar.") from error
    except OSError as error:
        raise ValueError(f"Frame kamera tidak dapat diproses: {error}") from error

    encoded = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError("Frame kamera tidak dapat dibaca sebagai gambar.")

    image = cv2.GaussianBlur(image, (3, 3), 0)
    if float(np.std(image)) < 7:
        return {"cover_detected": False, "text_detected": False, "text_lines": 0}

    corners = _find_cover_corners(image)
    if corners is None:
        return {"cover_detected": False, "text_detected": False, "text_lines": 0}

    cover = _rectify_cover(image, corners)
    line_count = _text_line_count(_text_character_boxes(cover))
    return {
        "cover_detected": True,
        "text_detected": line_count > 0,
        "text_lines": line_count,
    }

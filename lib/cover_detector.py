from io import BytesIO
from statistics import pstdev

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError


MAX_FRAME_PIXELS = 320 * 240


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
        return {"text_detected": False, "text_lines": 0}

    line_count = _text_line_count(_text_character_boxes(image))
    return {"text_detected": line_count > 0, "text_lines": line_count}

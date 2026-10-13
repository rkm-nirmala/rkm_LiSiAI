from io import BytesIO
from statistics import mean

from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError
from pytesseract import (
    Output,
    TesseractError,
    TesseractNotFoundError,
    get_languages,
    image_to_data,
)

from lib.cover_detector import detect_text_regions


SUPPORTED_LANGUAGES = ("ind", "eng", "ind+eng")
MAX_IMAGE_PIXELS = 25_000_000


class OCRServiceError(Exception):
    def __init__(self, message, status_code=500, install_hint=None):
        super().__init__(message)
        self.status_code = status_code
        self.install_hint = install_hint


def _prepare_image(upload):
    with Image.open(upload) as source:
        if source.width * source.height > MAX_IMAGE_PIXELS:
            raise ValueError("Resolusi gambar terlalu besar. Batas maksimum adalah 25 megapiksel.")

        image = ImageOps.exif_transpose(source).convert("L")

    if max(image.size) < 1200:
        scale = 1200 / max(image.size)
        image = image.resize(
            (round(image.width * scale), round(image.height * scale)),
            Image.Resampling.LANCZOS,
        )

    image = ImageOps.autocontrast(image)
    return image


def _crop_to_text_regions(image):
    thumbnail = image.copy()
    thumbnail.thumbnail((320, 240), Image.Resampling.LANCZOS)
    frame = BytesIO()
    thumbnail.save(frame, format="JPEG", quality=85)
    detection = detect_text_regions(frame.getvalue())
    text_boxes = detection["text_boxes"]
    if not text_boxes:
        return image, None

    scale_x = image.width / thumbnail.width
    scale_y = image.height / thumbnail.height
    left = min(box[0] for box in text_boxes)
    top = min(box[1] for box in text_boxes)
    right = max(box[0] + box[2] for box in text_boxes)
    bottom = max(box[1] + box[3] for box in text_boxes)
    padding_x = max(12, round((right - left) * 0.12))
    padding_y = max(12, round((bottom - top) * 0.35))
    bounds = (
        max(0, round((left - padding_x) * scale_x)),
        max(0, round((top - padding_y) * scale_y)),
        min(image.width, round((right + padding_x) * scale_x)),
        min(image.height, round((bottom + padding_y) * scale_y)),
    )
    crop_width = bounds[2] - bounds[0]
    crop_height = bounds[3] - bounds[1]
    if (
        crop_width <= 0
        or crop_height <= 0
        or crop_width * crop_height >= image.width * image.height * 0.95
    ):
        return image, None

    return image.crop(bounds), bounds


def extract_text(upload, language="ind+eng"):
    if language not in SUPPORTED_LANGUAGES:
        raise OCRServiceError(
            "Bahasa harus salah satu dari: ind, eng, atau ind+eng.",
            status_code=400,
        )

    try:
        image = _prepare_image(upload)
    except UnidentifiedImageError as error:
        raise OCRServiceError(
            "File tidak dapat dikenali sebagai gambar yang valid.",
            status_code=400,
        ) from error
    except Image.DecompressionBombError as error:
        raise OCRServiceError(
            "Resolusi gambar terlalu besar untuk diproses.",
            status_code=400,
        ) from error
    except (OSError, ValueError) as error:
        raise OCRServiceError(
            f"Gambar tidak dapat diproses: {error}",
            status_code=400,
        ) from error

    image, crop_bounds = _crop_to_text_regions(image)
    image = image.filter(ImageFilter.UnsharpMask(radius=1.2, percent=140, threshold=3))

    try:
        installed_languages = set(get_languages(config=""))
    except TesseractNotFoundError as error:
        raise OCRServiceError(
            "Tesseract belum terpasang. Pasang Tesseract OCR beserta data bahasa yang diperlukan.",
            status_code=503,
        ) from error

    missing_languages = set(language.split("+")) - installed_languages
    if missing_languages:
        raise OCRServiceError(
            f"Data bahasa Tesseract belum tersedia: {', '.join(sorted(missing_languages))}.",
            status_code=503,
            install_hint="Pasang paket tesseract-ocr-ind dan/atau tesseract-ocr-eng.",
        )

    try:
        result = image_to_data(
            image,
            lang=language,
            config="--oem 1 --psm 11",
            output_type=Output.DICT,
        )
    except TesseractNotFoundError as error:
        raise OCRServiceError(
            "Tesseract belum terpasang atau tidak ditemukan di PATH.",
            status_code=503,
        ) from error
    except TesseractError as error:
        raise OCRServiceError(
            f"Tesseract gagal memproses gambar: {error}",
            status_code=500,
        ) from error

    recognized_words = []
    lines = {}
    for word, confidence, block, paragraph, line in zip(
        result["text"],
        result["conf"],
        result["block_num"],
        result["par_num"],
        result["line_num"],
    ):
        word = word.strip()
        confidence = float(confidence)
        if word and confidence >= 0:
            recognized_words.append((word, confidence))
            lines.setdefault((block, paragraph, line), []).append(word)

    return {
        "text": "\n".join(" ".join(words) for words in lines.values()),
        "language": language,
        "confidence": round(mean(confidence for _word, confidence in recognized_words), 2)
        if recognized_words
        else None,
        "crop_applied": crop_bounds is not None,
        "crop_bounds": list(crop_bounds) if crop_bounds is not None else None,
    }

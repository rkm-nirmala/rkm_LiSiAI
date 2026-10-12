from statistics import mean

from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError
from pytesseract import (
    Output,
    TesseractError,
    TesseractNotFoundError,
    get_languages,
    image_to_data,
)


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
    return image.filter(ImageFilter.UnsharpMask(radius=1.2, percent=140, threshold=3))


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
    }

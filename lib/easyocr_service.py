import os
from functools import lru_cache
from statistics import mean

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from lib.ocr_service import OCRServiceError, MAX_IMAGE_PIXELS, SUPPORTED_LANGUAGES


EASYOCR_LANGUAGES = {
    "ind": ("id",),
    "eng": ("en",),
    "ind+eng": ("id", "en"),
}


def _prepare_image(upload):
    with Image.open(upload) as source:
        if source.width * source.height > MAX_IMAGE_PIXELS:
            raise ValueError("Resolusi gambar terlalu besar. Batas maksimum adalah 25 megapiksel.")

        image = ImageOps.exif_transpose(source).convert("RGB")

    if max(image.size) < 1200:
        scale = 1200 / max(image.size)
        image = image.resize(
            (round(image.width * scale), round(image.height * scale)),
            Image.Resampling.LANCZOS,
        )

    return np.asarray(image)


@lru_cache(maxsize=1)
def _get_reader(languages, model_directory, download_enabled):
    try:
        import easyocr
    except (ImportError, OSError, RuntimeError) as error:
        raise OCRServiceError(
            f"EasyOCR tidak dapat dimuat: {error}",
            status_code=503,
            install_hint="Pasang dependensi EasyOCR dan PyTorch dari requirements.txt.",
        ) from error

    options = {"gpu": False, "download_enabled": download_enabled}
    if model_directory:
        options["model_storage_directory"] = model_directory
    try:
        return easyocr.Reader(list(languages), **options)
    except (OSError, RuntimeError, ValueError) as error:
        raise OCRServiceError(
            f"EasyOCR gagal dimulai. Periksa ketersediaan model bahasa dan direktori model: {error}",
            status_code=503,
            install_hint=(
                "Siapkan model EasyOCR saat masih online, lalu gunakan direktori model yang sama "
                "untuk operasi offline."
            ),
        ) from error


def _format_detections(detections):
    lines = []
    for box, text, confidence in detections:
        if not isinstance(text, str) or not text.strip():
            continue
        points = np.asarray(box, dtype=float)
        left = float(points[:, 0].min())
        top = float(points[:, 1].min())
        bottom = float(points[:, 1].max())
        lines.append(
            {
                "center_y": (top + bottom) / 2,
                "left": left,
                "height": max(1.0, bottom - top),
                "text": text.strip(),
                "confidence": float(confidence),
            }
        )

    grouped_lines = []
    for item in sorted(lines, key=lambda entry: entry["center_y"]):
        matching_line = next(
            (
                line
                for line in grouped_lines
                if abs(item["center_y"] - line["center_y"])
                <= max(item["height"], line["height"]) * 0.5
            ),
            None,
        )
        if matching_line is None:
            grouped_lines.append(
                {
                    "center_y": item["center_y"],
                    "height": item["height"],
                    "items": [item],
                }
            )
        else:
            matching_line["items"].append(item)
            matching_line["center_y"] = mean(entry["center_y"] for entry in matching_line["items"])
            matching_line["height"] = max(matching_line["height"], item["height"])

    grouped_lines.sort(key=lambda line: line["center_y"])
    text = "\n".join(
        " ".join(item["text"] for item in sorted(line["items"], key=lambda entry: entry["left"]))
        for line in grouped_lines
    )
    scores = [item["confidence"] for item in lines]
    return {
        "text": text,
        "confidence": round(mean(scores) * 100, 2) if scores else None,
    }


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

    languages = EASYOCR_LANGUAGES[language]
    model_directory = os.getenv("EASYOCR_MODEL_DIRECTORY", "").strip()
    download_enabled_value = os.getenv("EASYOCR_DOWNLOAD_ENABLED", "false").strip().lower()
    if download_enabled_value not in ("true", "false"):
        raise OCRServiceError(
            "EASYOCR_DOWNLOAD_ENABLED harus bernilai 'true' atau 'false'.",
            status_code=500,
        )
    download_enabled = download_enabled_value == "true"

    reader = _get_reader(languages, model_directory, download_enabled)
    try:
        detections = reader.readtext(image, detail=1, paragraph=False)
    except (OSError, RuntimeError, ValueError) as error:
        raise OCRServiceError(
            f"EasyOCR gagal memproses gambar: {error}",
            status_code=500,
        ) from error

    result = _format_detections(detections)
    result["language"] = language
    return result

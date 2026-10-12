from collections import deque
from datetime import datetime, timezone
from itertools import count
from statistics import mean

from flask import Flask, jsonify, render_template, request
from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError
from pytesseract import Output, TesseractError, TesseractNotFoundError, get_languages, image_to_data


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
OCR_LANGUAGES = {"ind": "ind", "eng": "eng", "ind+eng": "ind+eng"}
MAX_IMAGE_PIXELS = 25_000_000

sensor_readings = deque(maxlen=1000)
reading_ids = count(1)


def prepare_ocr_image(upload):
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


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/ocr", methods=["GET", "POST"])
def ocr():
    if request.method == "GET":
        return jsonify(
            message="Kirim gambar sampul melalui multipart/form-data dengan field 'image'.",
            method="POST",
            field="image",
            languages=list(OCR_LANGUAGES),
        )

    image = request.files.get("image")
    if image is None or not image.filename:
        return jsonify(error="Kirim gambar melalui field multipart/form-data 'image'."), 400
    language = request.form.get("language", "ind+eng")
    if language not in OCR_LANGUAGES:
        return jsonify(error="Bahasa harus salah satu dari: ind, eng, atau ind+eng."), 400

    try:
        processed_image = prepare_ocr_image(image.stream)
    except UnidentifiedImageError:
        return jsonify(error="File tidak dapat dikenali sebagai gambar yang valid."), 400
    except Image.DecompressionBombError:
        return jsonify(error="Resolusi gambar terlalu besar untuk diproses."), 400
    except (OSError, ValueError) as error:
        return jsonify(error=f"Gambar tidak dapat diproses: {error}"), 400

    try:
        installed_languages = set(get_languages(config=""))
    except TesseractNotFoundError:
        return jsonify(error="Tesseract belum terpasang. Pasang Tesseract OCR beserta data bahasa yang diperlukan."), 503

    missing_languages = set(language.split("+")) - installed_languages
    if missing_languages:
        return jsonify(
            error=f"Data bahasa Tesseract belum tersedia: {', '.join(sorted(missing_languages))}.",
            install_hint="Pasang paket tesseract-ocr-ind dan/atau tesseract-ocr-eng.",
        ), 503

    try:
        result = image_to_data(
            processed_image,
            lang=language,
            config="--oem 1 --psm 11",
            output_type=Output.DICT,
        )
    except TesseractNotFoundError:
        return jsonify(error="Tesseract belum terpasang atau tidak ditemukan di PATH."), 503
    except TesseractError as error:
        return jsonify(error=f"Tesseract gagal memproses gambar: {error}"), 500

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

    return jsonify(
        text="\n".join(" ".join(words) for words in lines.values()),
        language=language,
        confidence=round(mean(confidence for _word, confidence in recognized_words), 2)
        if recognized_words
        else None,
    )


@app.post("/ask")
def ask():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Body harus berupa JSON object."), 400

    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return jsonify(error="Field 'prompt' wajib berupa teks dan tidak boleh kosong."), 400

    return jsonify(
        error="Integrasi dengan Ollama belum diimplementasikan.",
        prompt=prompt.strip(),
    ), 501


@app.route("/sensor", methods=["GET", "POST"])
def sensor():
    if request.method == "GET":
        return jsonify(readings=list(sensor_readings))

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not payload:
        return jsonify(error="Body harus berupa JSON object berisi data sensor."), 400

    reading = {
        "id": next(reading_ids),
        "received_at": datetime.now(timezone.utc).isoformat(),
        "data": payload,
    }
    sensor_readings.append(reading)
    return jsonify(reading), 201


@app.get("/monitor")
def monitor():
    return render_template("monitor.html")


@app.get("/scan")
def scan():
    return render_template("scan.html")


@app.errorhandler(413)
def request_entity_too_large(_error):
    return jsonify(error="Ukuran gambar melebihi batas 16 MB."), 413


if __name__ == "__main__":
    app.run(debug=True)

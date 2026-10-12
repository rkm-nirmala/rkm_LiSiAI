from collections import deque
from datetime import datetime, timezone
from itertools import count

from flask import Flask, jsonify, render_template, request


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

sensor_readings = deque(maxlen=1000)
reading_ids = count(1)


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
            message="Endpoint OCR siap menerima gambar; pemrosesan Tesseract belum diimplementasikan.",
            method="POST",
            field="image",
        )

    image = request.files.get("image")
    if image is None or not image.filename:
        return jsonify(error="Kirim gambar melalui field multipart/form-data 'image'."), 400
    if not image.mimetype or not image.mimetype.startswith("image/"):
        return jsonify(error="File yang dikirim harus berupa gambar."), 400

    return jsonify(
        error="Gambar diterima, tetapi pemrosesan OCR dengan Tesseract belum diimplementasikan."
    ), 501


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

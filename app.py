import math
from datetime import datetime, timezone
from itertools import count

from flask import Flask, jsonify, render_template, request

from data.book_scan import BookScanDataError, build_book_scan_data
from data.sensor_analysis import SensorAnalysisDataError, build_sensor_analysis_data
from lib.ask_service import AskServiceError, ask_ollama
from lib.cover_detector import detect_text_regions
from lib.ocr_service import OCRServiceError, SUPPORTED_LANGUAGES, extract_text


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

reading_ids = count(1)
latest_sensor_reading = None


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
            languages=list(SUPPORTED_LANGUAGES),
        )

    image = request.files.get("image")
    if image is None or not image.filename:
        return jsonify(error="Kirim gambar melalui field multipart/form-data 'image'."), 400
    language = request.form.get("language", "ind+eng")
    try:
        result = extract_text(image.stream, language)
    except OCRServiceError as error:
        response = {"error": str(error)}
        if error.install_hint:
            response["install_hint"] = error.install_hint
        return jsonify(response), error.status_code

    return jsonify(result)


@app.post("/detect-text")
def detect_text():
    image = request.files.get("image")
    if image is None or not image.filename:
        return jsonify(error="Kirim frame kamera melalui multipart field 'image'."), 400

    try:
        return jsonify(detect_text_regions(image.stream.read()))
    except ValueError as error:
        return jsonify(error=str(error)), 400


@app.post("/ask")
def ask():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Body harus berupa JSON object."), 400

    task = payload.get("task")
    try:
        if task == "book_scan":
            data = build_book_scan_data(payload.get("extracted_text"))
        elif task == "sensor_analysis":
            data = build_sensor_analysis_data(
                payload.get("question"),
                payload.get("latest_reading"),
            )
        else:
            return jsonify(error="Field 'task' harus 'book_scan' atau 'sensor_analysis'."), 400
    except (BookScanDataError, SensorAnalysisDataError) as error:
        return jsonify(error=str(error)), 400

    try:
        return jsonify(ask_ollama(task, data))
    except AskServiceError as error:
        return jsonify(error=str(error)), error.status_code


@app.route("/sensor", methods=["GET", "POST"])
def sensor():
    global latest_sensor_reading

    if request.method == "GET":
        return jsonify(reading=latest_sensor_reading)

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not payload:
        return jsonify(error="Body harus berupa JSON object berisi data sensor."), 400
    if not isinstance(payload.get("device"), str) or not payload["device"].strip():
        return jsonify(error="Field 'device' wajib berupa teks dan tidak boleh kosong."), 400
    if not isinstance(payload.get("status"), str) or not payload["status"].strip():
        return jsonify(error="Field 'status' wajib berupa teks dan tidak boleh kosong."), 400

    numeric_fields = (
        "moisture_raw",
        "soil_moisture_pct",
        "soil_temperature",
        "air_temperature",
        "air_humidity",
        "temperature",
        "humidity",
    )
    for field in numeric_fields:
        value = payload.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return jsonify(error=f"Field '{field}' wajib berupa angka."), 400
        if isinstance(value, float) and not math.isfinite(value):
            return jsonify(error=f"Field '{field}' harus berupa angka finite."), 400

    reading = {
        "id": next(reading_ids),
        "received_at": datetime.now(timezone.utc).isoformat(),
        "data": payload,
    }
    latest_sensor_reading = reading
    return jsonify(reading), 201


@app.get("/monitor")
def monitor():
    return render_template("monitor.html")


@app.get("/scan")
def scan():
    return render_template("scan.html")


if __name__ == "__main__":
    app.run(debug=True)

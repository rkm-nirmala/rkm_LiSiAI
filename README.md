# LiSiAI

Aplikasi Flask untuk mengekstrak teks dari sampul buku dan memantau sensor ESP32 dengan analisis AI lokal.

## Menjalankan aplikasi

Tesseract dan data bahasa Indonesia serta Inggris diperlukan untuk menjalankan OCR:

```bash
sudo apt install tesseract-ocr tesseract-ocr-ind tesseract-ocr-eng
```

OpenCV untuk deteksi lokal terpasang sebagai dependensi Python melalui `requirements.txt`.
Pasang Ollama dan unduh model ringan sekali sebelum dipakai offline:

```bash
ollama pull qwen2.5:3b
```

Jalankan service Ollama di komputer server. Model yang sudah terunduh dapat digunakan tanpa koneksi internet.

Di Windows/macOS, pasang Tesseract OCR dan pastikan executable `tesseract` tersedia di `PATH`.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Buka `http://127.0.0.1:5000`.

## Endpoint

| Path | Kegunaan |
| --- | --- |
| `/` | Halaman sambutan dengan tombol menuju dashboard |
| `/dashboard` | Halaman dashboard awal |
| `/scan` | Membuka kamera, meminta deteksi teks OpenCV lokal, lalu capture otomatis dan menampilkan hasil OCR yang bisa diedit |
| `/ocr` | `POST` gambar sebagai multipart field `image`; field opsional `language` (`ind+eng`, `ind`, `eng`) |
| `/detect-text` | `POST` frame kamera berukuran kecil sebagai multipart field `image`; OpenCV mengembalikan garis sampul dan kotak teks yang terdeteksi |
| `/ask` | `POST` JSON dengan `task` `book_scan` + `extracted_text` atau `sensor_analysis` + `question` + `latest_reading`; diteruskan ke Ollama lokal |
| `/sensor` | `POST` JSON data sensor ESP32; mengganti satu-satunya data terbaru. `GET` mengembalikan `{"reading": ...}` |
| `/monitor` | Tampilan data sensor dan antarmuka pertanyaan AI |

OCR menggunakan Tesseract dengan preprocessing gambar ringan (orientasi EXIF, grayscale, peningkatan kontras, dan penajaman). Gambar dibatasi 16 MB dan 25 megapiksel. Respons sukses berisi teks, bahasa, dan rata-rata confidence kata yang terdeteksi. Jika executable atau data bahasa Tesseract belum tersedia, endpoint mengembalikan `503` dengan petunjuk pemasangan.

Halaman `/scan` memerlukan izin kamera browser dan koneksi HTTPS (localhost diperbolehkan). Tampilan dua kolom memperlihatkan kamera/foto hasil capture dan hasil OCR yang bisa diedit. Pesan status kamera tidak ditampilkan di sekitar preview; hanya indikator kamera dan status OCR yang tetap tersedia. Frame kecil dikirim setiap 700 ms hanya ke server Flask lokal. Preview memberi garis hijau pada kontur sampul dan kotak kuning pada baris teks yang ditemukan. OpenCV mencoba mendeteksi teks meski tepi sampul tidak terbaca; dalam kondisi itu capture otomatis perlu setidaknya dua baris teks, sementara sampul bertepi cukup jelas dapat lolos dengan satu baris. Auto-capture menunggu deteksi yang memenuhi syarat selama setidaknya 1,4 detik dan memastikan perubahan gambar antar-frame kecil selama tiga pemeriksaan berturut-turut. Ini tetap deteksi bentuk/pola offline, bukan model pengenal objek semantik.

Endpoint `/ask` menggunakan prompt terpisah di `prompts/` dan pembentuk data terstruktur di `data/`, lalu meneruskan permintaan ke Ollama pada `http://127.0.0.1:11434` secara default. Model default adalah `qwen2.5:3b`; sesuaikan dengan model yang tersedia memakai `OLLAMA_MODEL`. `OLLAMA_BASE_URL` dan `OLLAMA_TIMEOUT_SECONDS` juga dapat dikonfigurasi melalui environment. Teks OCR yang dikoreksi dikirim oleh tombol Tanya AI di halaman scan. Ollama perlu berjalan dan model sudah diunduh di server; setelah itu analisis berlangsung lokal tanpa layanan cloud. Respons koneksi Ollama yang gagal menghasilkan error HTTP eksplisit.

Data sensor terbaru disimpan di memori proses (satu bacaan saja) dan akan hilang saat aplikasi dimulai ulang. Halaman `/monitor` menampilkan bacaan tersebut dan mengirim bacaan yang sama bersama pertanyaan ke `/ask` untuk analisis lokal.

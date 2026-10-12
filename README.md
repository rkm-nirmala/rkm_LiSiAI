# LiSiAI

Aplikasi Flask untuk mengekstrak teks dari sampul buku dan memantau sensor ESP32 dengan analisis AI lokal.

## Menjalankan aplikasi

Tesseract dan data bahasa Indonesia serta Inggris diperlukan untuk menjalankan OCR:

```bash
sudo apt install tesseract-ocr tesseract-ocr-ind tesseract-ocr-eng
```

OpenCV untuk deteksi lokal terpasang sebagai dependensi Python melalui `requirements.txt`.

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
| `/ask` | `POST` JSON berisi `prompt`; integrasi Ollama belum tersedia |
| `/sensor` | `POST` JSON object untuk menyimpan data; `GET` untuk mengambil data |
| `/monitor` | Tampilan data sensor dan antarmuka pertanyaan AI |

OCR menggunakan Tesseract dengan preprocessing gambar ringan (orientasi EXIF, grayscale, peningkatan kontras, dan penajaman). Gambar dibatasi 16 MB dan 25 megapiksel. Respons sukses berisi teks, bahasa, dan rata-rata confidence kata yang terdeteksi. Jika executable atau data bahasa Tesseract belum tersedia, endpoint mengembalikan `503` dengan petunjuk pemasangan.

Halaman `/scan` memerlukan izin kamera browser dan koneksi HTTPS (localhost diperbolehkan). Tampilan dua kolom memperlihatkan kamera/foto hasil capture dan hasil OCR yang bisa diedit. Frame kecil dikirim setiap 700 ms hanya ke server Flask lokal. Preview memberi garis hijau pada kontur sampul dan kotak kuning pada baris teks yang ditemukan. OpenCV mencoba mendeteksi teks meski tepi sampul tidak terbaca; dalam kondisi itu capture otomatis perlu setidaknya dua baris teks, sementara sampul bertepi cukup jelas dapat lolos dengan satu baris. Capture otomatis menunggu deteksi yang memenuhi syarat selama tiga frame berturut-turut. Ini tetap deteksi bentuk/pola offline, bukan model pengenal objek semantik. Tombol tanya AI saat ini masih berupa stub UI; belum memanggil `/ask`.

Data sensor saat ini disimpan sementara di memori proses (maksimal 1.000 data terbaru) dan akan hilang saat aplikasi dimulai ulang. Integrasi Ollama pada `/ask` belum tersedia.

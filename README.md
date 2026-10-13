# LiSiAI

Aplikasi Flask untuk mengekstrak teks dari sampul buku dan memantau sensor ESP32 dengan analisis AI lokal.

## Menjalankan aplikasi

Untuk menggunakan engine Tesseract, pasang executable Tesseract dan data bahasa Indonesia serta Inggris:

```bash
sudo apt install tesseract-ocr tesseract-ocr-ind tesseract-ocr-eng
```

EasyOCR juga tersedia sebagai engine alternatif dan dipasang bersama dependensi Python. EasyOCR memakai PyTorch dan bobot model bahasa; instalasi/model awal dapat berukuran besar dan mengunduh file saat pertama kali dipakai. Siapkan cache model saat masih online sebelum menjalankan sistem sepenuhnya offline.

OpenCV untuk deteksi lokal terpasang sebagai dependensi Python melalui `requirements.txt`.
Pasang Ollama dan unduh model ringan sekali sebelum dipakai offline:

```bash
ollama pull qwen2.5:3b
```

Jalankan service Ollama di komputer server. Model yang sudah terunduh dapat digunakan tanpa koneksi internet.

Di Windows/macOS, jika memilih Tesseract, pasang executable OCR dan pastikan `tesseract` tersedia di `PATH`.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Untuk menjalankan endpoint dengan EasyOCR, pilih engine saat startup:

```bash
OCR_ENGINE=easyocr python app.py
```

Buka `http://127.0.0.1:5000`.

## Endpoint

| Path | Kegunaan |
| --- | --- |
| `/` | Halaman sambutan dengan tombol menuju dashboard |
| `/dashboard` | Halaman dashboard awal |
| `/scan` | Membuka kamera, meminta deteksi teks OpenCV lokal, lalu capture otomatis dan menampilkan hasil OCR yang bisa diedit |
| `/ocr` | `POST` gambar sebagai multipart field `image`; field opsional `language` (`ind+eng`, `ind`, `eng`). Engine dipilih di server melalui `OCR_ENGINE`. |
| `/detect-text` | `POST` frame kamera berukuran kecil sebagai multipart field `image`; OpenCV mengembalikan garis sampul dan kotak teks yang terdeteksi |
| `/ask` | `POST` JSON dengan `task` `book_scan` + `extracted_text` atau `sensor_analysis` + `question` + `latest_reading`; diteruskan ke Ollama lokal |
| `/sensor` | `POST` JSON data sensor ESP32; mengganti satu-satunya data terbaru. `GET` mengembalikan `{"reading": ...}` |
| `/monitor` | Tampilan data sensor dan antarmuka pertanyaan AI |

OCR mendukung dua engine yang memakai endpoint dan format respons `/ocr` yang sama. Default-nya adalah Tesseract; untuk mengganti engine, ubah `app.config["OCR_ENGINE"]` menjadi `"easyocr"` di `app.py`, atau jalankan `OCR_ENGINE=easyocr python app.py`, lalu restart aplikasi. Jangan menerima pilihan engine dari parameter publik request agar pemilihan tetap menjadi konfigurasi server. Respons GET `/ocr` menunjukkan engine aktif dan daftar engine yang tersedia. Respons POST menyertakan `engine`, `text`, `language`, dan `confidence` dalam skala 0–100 atau `null`. Skala numeriknya sama, tetapi confidence bawaan kedua engine tidak dikalibrasi untuk dibandingkan langsung.

Tesseract menggunakan preprocessing gambar (orientasi EXIF, grayscale, peningkatan kontras, dan penajaman), serta memerlukan executable dan data bahasa Tesseract pada sistem. EasyOCR menggunakan model bahasa Indonesia (`id`) dan Inggris (`en`), preprocessing RGB, dan berjalan pada CPU (`gpu=False`). Pembaca EasyOCR dimuat hanya ketika dipilih dan dipakai ulang dalam proses server. Kedua engine membatasi gambar sampai 25 megapiksel dan Flask membatasi request sampai 16 MB.

Untuk EasyOCR, `EASYOCR_MODEL_DIRECTORY` dapat menentukan lokasi cache model dan `EASYOCR_DOWNLOAD_ENABLED` menerima `true` atau `false` (default `false`, sehingga request OCR tidak mengunduh bobot secara diam-diam). Untuk menyiapkan deployment offline, set `EASYOCR_DOWNLOAD_ENABLED=true` saat menjalankan EasyOCR pada mesin yang online dan lakukan satu request OCR; setelah bobot bahasa tersimpan di direktori cache, matikan unduhan kembali. Jika bobot atau dependensi belum tersedia, endpoint mengembalikan error eksplisit dan tidak beralih diam-diam ke engine lain. Tesseract juga tetap memerlukan data bahasa yang telah dipasang.

Halaman `/scan` memerlukan izin kamera browser dan koneksi HTTPS (localhost diperbolehkan). Tampilan dua kolom memperlihatkan kamera/foto hasil capture dan hasil OCR yang bisa diedit. Pesan status kamera tidak ditampilkan di sekitar preview; hanya indikator kamera dan status OCR yang tetap tersedia. Frame kecil dikirim setiap 700 ms hanya ke server Flask lokal. Preview memberi garis hijau pada kontur sampul dan kotak kuning pada baris teks yang ditemukan. OpenCV mencoba mendeteksi teks meski tepi sampul tidak terbaca; dalam kondisi itu capture otomatis perlu setidaknya dua baris teks, sementara sampul bertepi cukup jelas dapat lolos dengan satu baris. Auto-capture menunggu deteksi yang memenuhi syarat selama setidaknya 1,4 detik dan memastikan perubahan gambar antar-frame kecil selama tiga pemeriksaan berturut-turut. Ini tetap deteksi bentuk/pola offline, bukan model pengenal objek semantik.

Endpoint `/ask` menggunakan prompt terpisah di `prompts/` dan pembentuk data terstruktur di `data/`, lalu meneruskan permintaan ke Ollama pada `http://127.0.0.1:11434` secara default. Model default adalah `qwen2.5:3b`; sesuaikan dengan model yang tersedia memakai `OLLAMA_MODEL`. `OLLAMA_BASE_URL` dan `OLLAMA_TIMEOUT_SECONDS` juga dapat dikonfigurasi melalui environment. Teks OCR yang dikoreksi dikirim oleh tombol Tanya AI di halaman scan. Ollama perlu berjalan dan model sudah diunduh di server; setelah itu analisis berlangsung lokal tanpa layanan cloud. Respons koneksi Ollama yang gagal menghasilkan error HTTP eksplisit.

Data sensor terbaru disimpan di memori proses (satu bacaan saja) dan akan hilang saat aplikasi dimulai ulang. Halaman `/monitor` menampilkan bacaan tersebut dan mengirim bacaan yang sama bersama pertanyaan ke `/ask` untuk analisis lokal.

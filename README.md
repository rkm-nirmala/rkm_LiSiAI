# LiSiAI

Aplikasi Flask untuk mengekstrak teks dari sampul buku dan memantau sensor ESP32 dengan analisis AI lokal.

## Menjalankan aplikasi

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
| `/scan` | Form untuk mengirim gambar sampul ke `/ocr` |
| `/ocr` | `POST` gambar sebagai multipart field `image`; integrasi Tesseract belum tersedia |
| `/ask` | `POST` JSON berisi `prompt`; integrasi Ollama belum tersedia |
| `/sensor` | `POST` JSON object untuk menyimpan data; `GET` untuk mengambil data |
| `/monitor` | Tampilan data sensor dan antarmuka pertanyaan AI |

Data sensor saat ini disimpan sementara di memori proses (maksimal 1.000 data terbaru) dan akan hilang saat aplikasi dimulai ulang. Endpoint `/ocr` dan `/ask` sengaja mengembalikan status `501 Not Implemented` sampai integrasi Tesseract dan Ollama ditambahkan.

# Ringkasan Sistem LiSiAI untuk Bahan Penulisan Paper

Dokumen ini merangkum implementasi aplikasi yang ada di repository sebagai bahan konteks bagi AI atau penulis paper. Dokumen ini **bukan hasil evaluasi ilmiah**. Bedakan fitur yang memang sudah diimplementasikan dari tujuan, asumsi, dan hal yang masih harus diuji.

## Prompt untuk AI penulis paper

Gunakan ringkasan teknis di bawah untuk membantu menyusun draf paper berbahasa Indonesia tentang LiSiAI.

Ketentuan penulisan:

1. Jelaskan LiSiAI sebagai prototipe aplikasi web untuk dua alur: ekstraksi teks sampul buku dan pemantauan sensor ESP32 dengan bantuan model AI lokal.
2. Uraikan arsitektur dan implementasi berdasarkan fakta di dokumen ini. Jangan mengklaim bahwa sistem telah diterapkan atau diuji di perpustakaan/daerah 3T jika bukti pengujian tersebut belum disediakan.
3. Jangan membuat angka akurasi OCR, precision/recall detektor, latensi, jumlah responden, hasil usability, efisiensi, atau perbandingan model. Tandai semua hasil tersebut sebagai **belum tersedia** dan usulkan cara mengukurnya.
4. Jangan menyebut detektor OpenCV sebagai model deep learning atau pengenal buku semantik. Detektor saat ini menggunakan heuristik citra berbasis OpenCV.
5. Jangan mengklaim semua kebutuhan operasional offline secara otomatis. Instalasi awal, pengunduhan model Ollama dan dependensi memerlukan persiapan; akses kamera browser pada perangkat klien mensyaratkan konteks aman seperti HTTPS atau localhost.
6. Jangan mengarang referensi, sitasi, hasil eksperimen, fakta bibliografi, atau klaim manfaat. Jika paper meminta tinjauan pustaka, tandai kebutuhan referensi yang perlu dicari dan diverifikasi secara terpisah.
7. Bedakan dengan jelas status **sudah diimplementasikan**, **batasan saat ini**, dan **rencana pengujian/pengembangan**.
8. Susun paper dengan bagian yang sesuai format akademik: judul, abstrak, kata kunci, pendahuluan, metode/perancangan sistem, implementasi, rencana atau hasil pengujian (hanya jika datanya disediakan), pembahasan, keterbatasan, kesimpulan, dan referensi terverifikasi.

## 1. Identitas dan tujuan aplikasi

- **Nama aplikasi:** LiSiAI.
- **Jenis:** prototipe aplikasi web berbasis Flask dengan antarmuka berbahasa Indonesia.
- **Tujuan fungsional:** membantu alur ekstraksi teks dari sampul buku; menerima dan menampilkan satu bacaan sensor ESP32 terbaru; meneruskan konteks buku atau sensor ke Ollama yang di-host pada layanan lokal.
- **Konteks penggunaan yang dituju:** akses informasi dan pemantauan tanaman, termasuk kemungkinan penggunaan pada lingkungan dengan internet terbatas. Kesesuaian dan manfaat untuk kondisi lapangan 3T masih perlu diuji langsung.
- **Teknologi inti:** Python, Flask, Pillow, pytesseract/Tesseract OCR, EasyOCR/PyTorch sebagai alternatif OCR, OpenCV (`opencv-python-headless`), JavaScript browser, serta Ollama melalui HTTP API lokal.
- **Antarmuka:** HTML/Jinja dan CSS responsif; pemrosesan kamera serta komunikasi endpoint dilakukan JavaScript di browser.

## 2. Gambaran arsitektur

```text
Perangkat pengguna / browser
  ├─ /scan: kamera → frame kecil → Flask /detect-text
  │                         ← deteksi kontur dan baris teks
  │         capture → Flask /ocr → OCR engine terkonfigurasi
  │         teks OCR yang diedit → Flask /ask
  └─ /monitor: GET /sensor → tampilan data
               pertanyaan + bacaan terbaru → Flask /ask

Flask (server aplikasi lokal)
  ├─ /detect-text → lib/cover_detector.py → OpenCV
  ├─ /ocr         → engine terpilih (Tesseract atau EasyOCR)
  ├─ /sensor      → satu bacaan terbaru dalam memori proses
  └─ /ask         → data/ + prompts/ + lib/ask_service.py
                                      ↓
                               Ollama HTTP API
                               /api/chat
```

Browser berkomunikasi dengan aplikasi Flask. Deteksi OpenCV berjalan pada server Flask, bukan di dalam browser. Flask kemudian mengakses Ollama pada URL yang dikonfigurasi server. Untuk penggunaan tanpa internet, browser tetap perlu terhubung ke server melalui jaringan yang dapat dijangkau (misalnya LAN lokal); “tanpa internet” tidak berarti tanpa jaringan lokal.

## 3. Halaman dan endpoint

| Path | Metode | Perilaku saat ini |
| --- | --- | --- |
| `/` | GET | Halaman sambutan dengan tombol menuju dashboard. |
| `/dashboard` | GET | Halaman pilihan fitur scan sampul dan monitor tanaman. |
| `/scan` | GET | Membuka kamera browser, menampilkan overlay deteksi, mengambil gambar otomatis atau manual, mengirim gambar untuk OCR, menyediakan teks untuk diedit dan tombol analisis AI. |
| `/detect-text` | POST | Menerima frame gambar multipart pada field `image`; mengembalikan status deteksi, koordinat kontur sampul bila ditemukan, jumlah baris teks, dan kotak teks. |
| `/ocr` | GET, POST | GET memberikan petunjuk request, bahasa, engine aktif, dan engine tersedia. POST menerima gambar pada field multipart `image` dan field opsional `language` (`ind`, `eng`, atau `ind+eng`; default `ind+eng`). Engine dipilih pada konfigurasi server `OCR_ENGINE`. |
| `/sensor` | GET, POST | POST menerima JSON bacaan sensor dan menggantikan bacaan sebelumnya. GET mengembalikan satu bacaan terbaru sebagai `{"reading": ...}`, atau `{"reading": null}` bila belum ada. |
| `/monitor` | GET | Menampilkan pembacaan sensor terbaru dan formulir pertanyaan AI. Data dimuat ulang dari `/sensor` setiap lima detik. |
| `/ask` | POST | Memvalidasi task dan data, membaca prompt yang sesuai, memanggil Ollama lokal, lalu mengembalikan jawaban, model, dan task. |

### Format bacaan sensor yang digunakan

Contoh payload yang diterima `/sensor`:

```json
{
  "device": "plant-esp32-01",
  "status": "online",
  "moisture_raw": 3083,
  "soil_moisture_pct": 5.7,
  "soil_temperature": 33.7,
  "air_temperature": 33.0,
  "air_humidity": 46.0,
  "temperature": 33.0,
  "humidity": 46.0
}
```

`device` dan `status` wajib berupa string yang tidak kosong. Ketujuh field pengukuran pada contoh wajib numerik; boolean, nilai nonnumerik, serta float non-finite ditolak. Field lain tidak secara eksplisit ditolak dan payload yang diterima disimpan sebagai `data`. Setiap bacaan dibungkus metadata `id` dan `received_at` dalam UTC. Validasi belum memeriksa rentang nilai, kalibrasi, identitas perangkat, autentikasi, atau kewajaran fisik pengukuran.

Contoh request `/ask` untuk hasil scan:

```json
{
  "task": "book_scan",
  "extracted_text": "Judul buku Nama Penulis"
}
```

Contoh request `/ask` untuk data sensor:

```json
{
  "task": "sensor_analysis",
  "question": "Bagaimana kondisi kelembapan tanaman?",
  "latest_reading": {
    "id": 1,
    "received_at": "2026-10-12T07:00:00+00:00",
    "data": {
      "device": "plant-esp32-01",
      "status": "online",
      "soil_moisture_pct": 5.7
    }
  }
}
```

Task yang diterima `/ask` adalah `book_scan` dan `sensor_analysis`. Teks scan dibatasi 12.000 karakter; pertanyaan sensor dibatasi 2.000 karakter. Jika layanan Ollama tidak tersedia, endpoint mengembalikan error HTTP seperti 503/504, bukan jawaban AI tiruan.

## 4. Alur scan sampul buku

1. Halaman `/scan` meminta akses kamera melalui `navigator.mediaDevices.getUserMedia`, dengan kamera belakang sebagai pilihan ideal. Akses kamera browser umumnya memerlukan HTTPS; localhost merupakan pengecualian yang dianggap konteks aman.
2. JavaScript membuat frame sampling dengan ukuran maksimum sekitar 320 × 240 piksel sesuai rasio video. Sampling dilakukan sekitar setiap 700 ms.
3. Frame sampling dikirim sebagai JPEG berukuran kecil ke endpoint `/detect-text` di server aplikasi. Tidak ada panggilan ke API deteksi cloud.
4. `lib/cover_detector.py` memvalidasi gambar tidak melebihi 320 × 240 piksel, mengubahnya menjadi grayscale dan memakai blur Gaussian. OpenCV menggunakan Canny contours dan penyederhanaan polygon untuk mencari calon bidang segi empat besar. Calon kontur dibatasi luas relatif, sudut, dan rasio aspek. Jika ditemukan, area perspektif diluruskan untuk membantu deteksi teks.
5. Deteksi pola karakter menggunakan MSER, penyaringan ukuran/rasio kotak, pengelompokan karakter ke baris, dan filter variasi dimensi/spasi. Bila kontur sampul ditemukan, keberadaan setidaknya satu baris teks dapat menghasilkan `text_detected=true`. Tanpa kontur sampul, diperlukan setidaknya dua baris teks. Ini adalah heuristik visi komputer, bukan OCR dan bukan pengenal kelas objek berbasis deep learning.
6. Respons deteksi memuat `cover_detected`, `cover_corners`, `text_detected`, `text_lines`, dan `text_boxes`. Browser menggambar garis hijau pada kontur sampul dan kotak kuning pada baris teks. Overlay merah digunakan ketika tidak ada kotak teks yang dikembalikan.
7. Auto-capture mensyaratkan teks terdeteksi sedikitnya tiga kali berturut-turut, perubahan rata-rata luminansi frame kecil (threshold `< 8`), dan kestabilan sekurangnya 1,4 detik. Tidak ada countdown. Pengguna juga dapat menekan tombol capture manual.
8. Setelah capture, kamera dihentikan dan foto tetap terlihat sebagai preview. Gambar resolusi capture dibatasi dengan sisi lebar maksimum 1.600 piksel, dikodekan sebagai JPEG kualitas 0,9, lalu dikirim ke `/ocr`.
9. Hasil OCR diubah menjadi satu baris dengan merapikan whitespace, ditampilkan pada textarea yang dapat diedit, dan dapat dikirim melalui tombol AI ke task `book_scan`.

### Pemrosesan OCR

Endpoint `/ocr` menggunakan implementasi yang dipilih oleh konfigurasi Flask `OCR_ENGINE`, yaitu `tesseract` (default) atau `easyocr`. Pemilihan engine adalah konfigurasi server, bukan parameter dari browser, sehingga alur kamera dan kontrak endpoint tetap sama saat backend diganti. Respons sukses menyertakan teks, bahasa, confidence pada skala 0–100 atau `null`, dan nama engine. Walau disajikan pada rentang numerik yang sama, confidence bawaan engine berbeda definisi dan tidak dapat dibandingkan langsung sebagai probabilitas terkalibrasi.

`lib/ocr_service.py` (Tesseract):

- Membaca format gambar yang dikenali Pillow; file tidak dipercaya hanya berdasarkan MIME type.
- Menolak gambar dengan resolusi lebih dari 25 megapiksel.
- Mengoreksi orientasi EXIF, mengubah ke grayscale, memperbesar gambar kecil hingga sisi terpanjang minimum 1.200 piksel, melakukan autocontrast, dan unsharp mask.
- Memastikan executable Tesseract dan data bahasa yang diminta tersedia.
- Memanggil pytesseract dengan `--oem 1 --psm 11` untuk deteksi teks dengan tata letak relatif bebas.
- Mengembalikan teks yang disusun per baris, bahasa, dan rata-rata confidence kata yang memiliki confidence nonnegatif. Jika tidak ada kata yang dikenali, confidence adalah `null`.
- Endpoint membatasi request body sampai 16 MB.

`lib/easyocr_service.py` (EasyOCR):

- Menggunakan model bahasa EasyOCR `id` untuk bahasa Indonesia dan `en` untuk bahasa Inggris; pilihan gabungan dipetakan ke kedua model.
- Mengoreksi orientasi EXIF, mengubah gambar menjadi RGB, dan memperbesar gambar kecil tanpa menerapkan preprocessing grayscale khusus Tesseract.
- Menjalankan inference pada CPU (`gpu=False`), menggunakan kembali Reader dalam proses Flask, mengelompokkan hasil deteksi ke baris, serta mengubah confidence ke skala 0–100.
- Memakai `EASYOCR_MODEL_DIRECTORY` untuk direktori model dan `EASYOCR_DOWNLOAD_ENABLED` untuk mengizinkan atau menolak unduhan bobot ketika model tidak tersedia. Unduhan dinonaktifkan secara default; operasi offline memerlukan bobot yang sudah disiapkan sebelumnya.

Bahasa antarmuka scan tidak meminta pemustaka memilih bahasa; scan mengirim nilai default `ind+eng`. Endpoint masih menyediakan parameter bahasa untuk pemanggil lain.

## 5. Alur monitor ESP32

1. Perangkat ESP32 mengirim JSON payload ke `POST /sensor`.
2. Flask memvalidasi keberadaan `device`, `status`, dan tujuh nilai numerik pengukuran; lalu mengganti `latest_sensor_reading` dengan bacaan yang baru diterima.
3. Halaman `/monitor` mengambil `GET /sensor`, menampilkan status perangkat, kelembapan tanah, suhu tanah, suhu dan kelembapan udara, serta waktu penerimaan. Polling berjalan setiap lima detik; tombol refresh juga tersedia.
4. Ketika pengguna mengajukan pertanyaan, halaman mengirim task `sensor_analysis`, pertanyaan, dan snapshot bacaan terbaru ke `/ask`.
5. Prompt sensor menginstruksikan Ollama menjawab berdasarkan data yang dikirim, tidak mengarang pengukuran, dan menyebutkan ketidakpastian satuan/konteks.

Walaupun UI menyebut sensor DS18B20 dan DHT11, backend menerima nilai yang diposting oleh perangkat dan tidak memverifikasi model fisik atau kalibrasi sensornya. Nama/unit itu harus diperlakukan sebagai rancangan integrasi, bukan hasil verifikasi perangkat keras.

## 6. Pemisahan prompt dan data untuk AI

- `prompts/book_scan.txt`: instruksi berbahasa Indonesia untuk mengidentifikasi judul/penulis jika terlihat, memberi ringkasan yang hanya didukung teks sampul, tidak mengarang fakta, dan mengakui ketidakpastian OCR.
- `prompts/sensor_analysis.txt`: instruksi untuk menafsirkan bacaan sensor, menyebut nilai/satuan jika tersedia, serta tidak membuat pengukuran atau diagnosis.
- `data/book_scan.py`: validasi teks hasil scan dan batas panjang, membentuk objek `extracted_text`.
- `data/sensor_analysis.py`: validasi pertanyaan/batas panjang dan membentuk objek pertanyaan serta bacaan terbaru.
- `lib/ask_service.py`: memilih file prompt berdasarkan task, mengambil pengaturan Ollama dari environment, mengirim system prompt dan JSON data sebagai pesan user ke `POST /api/chat`, lalu memvalidasi respons.

Teks OCR yang dikirim sebagai pesan user diperlakukan oleh system prompt sebagai data, bukan instruksi. Ini merupakan langkah desain prompt, bukan jaminan keamanan formal terhadap semua bentuk prompt injection atau keluaran model yang salah.

## 7. Konfigurasi dan menjalankan sistem

Dependensi Python ada di `requirements.txt`. Tesseract memerlukan executable sistem dan data bahasa Inggris/Indonesia. EasyOCR bergantung pada PyTorch dan bobot model bahasa yang perlu disiapkan sebelumnya untuk operasi offline. Ollama dan model harus disiapkan pada komputer server.

Engine OCR dapat diganti dengan mengubah `app.config["OCR_ENGINE"]` di `app.py` menjadi `tesseract` atau `easyocr`, atau mengatur environment `OCR_ENGINE` sebelum server dijalankan. Untuk EasyOCR, `EASYOCR_MODEL_DIRECTORY` mengatur cache model dan `EASYOCR_DOWNLOAD_ENABLED` dinonaktifkan secara default. Jika perlu menyiapkan bobot dari internet, unduhan dapat diaktifkan secara eksplisit terlebih dahulu; matikan kembali setelah model tersedia untuk operasi offline.

Model default dalam kode: `qwen2.5:3b`. Pengaturan:

| Variabel | Default | Fungsi |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | URL HTTP(S) Ollama yang dapat dijangkau server Flask. |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Nama model yang sudah tersedia di Ollama. |
| `OLLAMA_TIMEOUT_SECONDS` | `120` | Batas waktu request ke Ollama. |

Contoh persiapan pada sistem Debian/Ubuntu:

```bash
sudo apt install tesseract-ocr tesseract-ocr-ind tesseract-ocr-eng
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ollama pull qwen2.5:3b
python app.py
```

`ollama pull` memerlukan koneksi untuk pengunduhan awal model. Setelah executable, dependensi, data bahasa, dan model sudah dipasang, fungsi OCR/deteksi/AI dapat dijalankan tanpa layanan cloud asalkan browser dan server lokal tetap saling terhubung. Pengaturan default Ollama `127.0.0.1` menunjuk pada komputer tempat Flask berjalan, bukan komputer pengguna.

## 8. Batasan implementasi yang perlu dinyatakan

- Data sensor hanya disimpan dalam variabel memori proses. Data hilang saat restart; tidak ada basis data, histori, retensi, atau grafik riwayat.
- Buku yang dipindai, foto capture, dan hasil OCR tidak disimpan sebagai katalog/persistensi aplikasi. Foto dikirim untuk OCR; browser menggunakan URL sementara untuk preview.
- Tidak ada login, kontrol akses, autentikasi ESP32, TLS yang disediakan aplikasi, pembatasan laju, atau pengelolaan banyak perangkat. HTTPS untuk kamera perlu disediakan pada deployment.
- `app.py` menjalankan server Flask development dengan `debug=True` ketika dieksekusi langsung; konfigurasi tersebut bukan rekomendasi deployment publik/produksi.
- Detektor cover/text adalah heuristik OpenCV dan bisa gagal pada pencahayaan rendah, blur, perspektif ekstrem, sampul tanpa batas tegas, huruf dekoratif, ilustrasi mirip karakter, atau latar kompleks. Bentuk persegi dengan tulisan juga berpotensi salah dianggap sampul. Ia tidak mengenali identitas buku.
- Deteksi teks untuk pemicu capture berbeda dari engine OCR final yang dipilih. Deteksi keberadaan pola teks tidak membuktikan teks dapat dibaca dengan benar.
- OCR Tesseract maupun EasyOCR dapat salah, khususnya karena resolusi, pantulan, orientasi, font, bahasa campuran, atau tata letak sampul.
- AI menghasilkan jawaban dari model lokal; ringkasan isi buku tidak dapat dipastikan hanya dari teks sampul. Prompt meminta model mengakui keterbatasan, tetapi keluaran tetap perlu diverifikasi.
- Keberhasilan komunikasi Ollama lokal bergantung pada service aktif, model tersedia, kapasitas perangkat, dan konfigurasi URL/timeout. Kinerja/kemampuan model belum dibandingkan.
- Tidak ada angka performa/akurasi yang dapat disimpulkan dari keberadaan kode atau uji fungsi saja.

## 9. Status pengujian dan rencana evaluasi paper

Implementasi kode dapat diperiksa untuk endpoint, validasi, payload, dan perilaku UI. Pengujian dengan mock dapat memverifikasi integrasi perangkat lunak, tetapi tidak mengukur performa sistem nyata. Dokumen/repository ini tidak memuat dataset lapangan, protokol eksperimen, hasil kuantitatif, uji pengguna, ataupun hasil pengukuran latency yang tervalidasi.

Sebelum menyusun klaim hasil paper, rancang dan dokumentasikan setidaknya:

1. **Dataset sampul**: jumlah dan sumber gambar, izin penggunaan, variasi jenis buku, bahasa, ukuran teks, kondisi cahaya, sudut, jarak, pantulan, latar, blur; pisahkan data tuning dan uji.
2. **Kualitas OCR**: bandingkan Tesseract dan EasyOCR pada gambar uji yang sama menggunakan transkripsi ground truth dan metrik seperti Character Error Rate (CER) serta Word Error Rate (WER), cara normalisasi teks, dan jumlah sampel. Laporkan per kondisi/bahasa jika jumlah data mendukung.
3. **Deteksi dan auto-capture**: anotasi apakah sampul/teks terlihat, hitung true/false positive dan false negative, precision/recall/F1, false captures per durasi, waktu dari sampul stabil hingga capture, serta kondisi yang menyebabkan kegagalan. Definisikan ground truth dan ambang operasional sebelum tes.
4. **Sistem sensor**: variasi payload valid/tidak valid, frekuensi request, pergantian perangkat, nilai ekstrem, perilaku restart dan kehilangan data. Bandingkan dengan alat ukur acuan hanya bila tersedia dan terkalibrasi.
5. **AI lokal**: model dan versinya, quantization jika digunakan, konfigurasi Ollama, prompt yang diuji, kualitas factuality/relevansi dengan rubrik jelas, waktu respons, konsumsi RAM/CPU/GPU, serta penilaian manusia bila dilakukan.
6. **Kegunaan dan konteks 3T**: jumlah/karakteristik pengguna, perangkat dan browser, kualitas jaringan lokal, kebutuhan listrik, literasi digital, persetujuan partisipan, prosedur etika, dan hasil observasi yang nyata. Jangan menyatakan kelayakan lapangan sebelum diuji.
7. **Offline dan privasi**: catat prosedur memastikan request tidak keluar jaringan lokal, aset/dependensi yang dipasang, serta perilaku ketika internet tidak tersedia tetapi LAN/server masih beroperasi. Kamera tetap membutuhkan akses browser yang aman.
8. **Keterulangan eksperimen**: versi kode, perangkat keras, OS, versi Tesseract dan traineddata, versi EasyOCR/PyTorch dan bobot model, versi OpenCV/Pillow, model Ollama, konfigurasi kamera, tanggal, serta script/dataset uji bila boleh dibagikan.

## 10. Ringkasan kontribusi yang dapat diusulkan (belum diklaim terbukti)

Sebagai fokus paper prototipe, kontribusi dapat dirumuskan sebagai:

- integrasi pipeline kamera browser, deteksi pola teks/area sampul dengan OpenCV lokal, dan dua pilihan engine OCR (Tesseract atau EasyOCR) untuk alur scan interaktif;
- antarmuka scan dua kolom yang menampilkan preview/overlay, memungkinkan koreksi teks OCR, dan meneruskan teks yang sudah diedit ke model lokal;
- jembatan `/ask` dengan instruksi dan struktur data terpisah untuk task buku dan sensor;
- penerimaan serta visualisasi satu bacaan ESP32 terbaru dan konteks bacaan tersebut untuk pertanyaan AI.

Rumusan kontribusi ini menjelaskan artefak perangkat lunak, bukan bukti peningkatan akurasi, dampak literasi, atau efektivitas agronomis.

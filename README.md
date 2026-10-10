# SIRA — Sistem Informasi dan Referensi Aparatur

**Asisten Informasi SDM Polri berbasis dokumen.** SIRA adalah prototype aplikasi *Question and Answer* berbasis **Retrieval-Augmented Generation (RAG)**. Pengguna bertanya dengan bahasa sehari-hari, lalu SIRA mencari bagian dokumen yang paling relevan dan menjawab hanya berdasarkan isi dokumen tersebut, disertai referensi **nama dokumen dan halaman**.

Prototype ini dibuat untuk Seleksi Kemampuan Pemrograman Tahap 2 (RAG), 8–14 Oktober 2026. Bahan uji knowledge base:

- **Peraturan Kepolisian Nomor 1 Tahun 2025** — dokumen peraturan (pasal, ayat, tabel, rumus) tentang penilaian kinerja/SIPK. PDF teks.
- **Pengumuman Seleksi SBP dari Tamtama ke Bintara T.A. 2027** — dokumen pengumuman (persyaratan, tahapan, jadwal). PDF hasil scan, membutuhkan OCR.

Instalasi baru **langsung berisi kedua dokumen tersebut** sebagai knowledge base bawaan, sehingga SIRA bisa langsung ditanya tanpa upload, OCR, atau biaya AI. Dokumen bawaan bukan data mati: admin tetap dapat mengubah judul, mengganti file, menghapus, dan menambah dokumen baru melalui halaman `/admin`. Lihat [Knowledge base bawaan](#knowledge-base-bawaan).

## Daftar isi

1. [Fitur utama](#fitur-utama)
2. [Tech stack](#tech-stack)
3. [Arsitektur dan workflow RAG](#arsitektur-dan-workflow-rag)
4. [Instalasi](#instalasi)
5. [Penggunaan](#penggunaan)
6. [Dokumentasi API](#dokumentasi-api)
7. [Struktur proyek dan database](#struktur-proyek-dan-database)
8. [Pengujian](#pengujian)
9. [Keterbatasan dan pengembangan lanjutan](#keterbatasan-dan-pengembangan-lanjutan)
10. [Troubleshooting](#troubleshooting)

## Fitur utama

**Halaman chat (`/`)**

- Satu halaman berisi riwayat pesan, kotak pertanyaan, tombol **Kirim**, dan tombol **Percakapan baru**.
- Jawaban tampil bertahap (streaming) dengan referensi nama dokumen dan halaman, tanpa tautan atau unduhan PDF.
- Jika informasi tidak ada di dokumen, SIRA menyatakan informasi belum ditemukan dan tidak mengarang.
- Pertanyaan lanjutan ("kalau untuk lulusan SMA?") memahami topik sebelumnya. Jika konteks belum cukup, SIRA meminta klarifikasi.
- Riwayat percakapan tetap ada setelah refresh, browser ditutup, atau aplikasi di-restart. Hanya **Percakapan baru** yang menghapusnya.
- Sapaan dan pertanyaan perkenalan ("kamu siapa?", "SIRA itu apa?") dijawab langsung tanpa memanggil AI.

**Halaman admin (`/admin`)**

- Login satu akun admin (password di-hash Argon2).
- Upload PDF teks maupun scan (default maks. 100 MiB dan 300 halaman), ubah judul, ganti file (versi baru), dan hapus dokumen.
- Progres pemrosesan di background. Versi lama tetap aktif sampai versi baru berhasil.
- **Review dan koreksi**: menampilkan gambar asli halaman berdampingan dengan editor teks, untuk memperbaiki hasil OCR yang meragukan sebelum diindeks.
- **Uji koneksi AI** untuk memastikan layanan AI dapat dihubungi.

## Tech stack

| Bagian | Teknologi | Peran |
| --- | --- | --- |
| Frontend | React 19, TypeScript, Vite 7, CSS | UI chat dan admin |
| Backend | Python 3.12, FastAPI, Uvicorn | REST API, autentikasi, ingestion, retrieval, streaming, menyajikan hasil build frontend |
| Database aplikasi | SQLite | Akun admin, dokumen dan versinya, teks halaman, chunk, status ingestion, riwayat chat |
| Vector database | ChromaDB (PersistentClient, cosine) | Menyimpan embedding dan pencarian kemiripan secara lokal |
| Ekstraksi PDF | pdfplumber | Teks per halaman, termasuk tabel berdasarkan posisi karakter dan garis sel |
| Render PDF | pypdfium2, Pillow | Mengubah halaman scan menjadi gambar |
| OCR lokal | Tesseract (`ind` + `eng`), pytesseract | Membaca halaman scan di PC |
| OCR AI | GPT-6 Luna, fallback GPT-5.6 Sol | Membaca gambar halaman scan yang belum lolos pemeriksaan lokal |
| Tokenizer | tiktoken (`cl100k_base`) | Mengukur ukuran chunk |
| Embedding | OpenAI `text-embedding-3-small` (1536 dimensi) | Embedding chunk dan pertanyaan |
| LLM jawaban | OpenAI GPT-6 Luna (temperature 0.1) | Menyusun jawaban dari sumber yang ditemukan |
| Relay AI | Cloudflare Workers (TypeScript), Durable Object, Secrets | Menyimpan API key OpenAI di server, membatasi model, operasi, dan kecepatan |
| Pengujian | pytest, ruff, `node --test`, Miniflare | Tes backend dan relay dengan AI tiruan |

Pipeline RAG ditulis langsung tanpa framework orkestrasi (LangChain dan sejenisnya) agar setiap langkah mudah diperiksa.

## Arsitektur dan workflow RAG

```text
Browser (chat / admin)
        │
        ▼
FastAPI lokal (127.0.0.1) ──► Cloudflare Worker relay ──► OpenAI
        │                      (API key di Secrets)        (embedding, GPT-6 Luna, GPT-5.6 Sol)
        ▼
SQLite + file PDF + ChromaDB  (semua tersimpan lokal di folder data/)
```

PDF, teks hasil ekstraksi, dan vector database tersimpan di PC. Yang dikirim ke AI hanya teks chunk (saat embedding), potongan sumber yang relevan (saat menjawab), dan gambar halaman scan yang perlu dibaca AI.

### 1. Ingestion dan parsing dokumen

```text
Upload PDF → validasi → ekstraksi per halaman → (scan) OCR lokal → GPT-6 Luna → GPT-5.6 Sol → review manual bila perlu
          → chunking → embedding → simpan ke Chroma → aktifkan versi
```

- **Validasi**: hanya PDF; file rusak, terenkripsi, atau melebihi batas ukuran/halaman ditolak.
- **PDF teks** dibaca langsung. Tabel disusun dari posisi karakter dan batas sel asli, termasuk sel gabungan, lalu diubah menjadi baris-baris yang utuh. Detail: [ekstraksi tabel native](docs/native-pdf-tables.md).
- **PDF scan** dibaca Tesseract lokal terlebih dahulu. Area yang hasilnya meragukan (angka, tanggal, pangkat, negasi, tabel) dibaca ulang oleh GPT-6 Luna langsung dari gambar asli; bagian yang masih ragu dibaca GPT-5.6 Sol. Jika tetap belum lolos, admin mengonfirmasi lewat **Review dan koreksi**. Detail: [alur OCR](docs/ocr-fallback.md).

### 2. Strategi chunking

- Chunk dibuat **per halaman**, sehingga setiap chunk selalu memiliki nomor halaman sumber yang jelas.
- Teks dipecah di batas paragraf, lalu digabung sampai sekitar **650 token**. Paragraf yang lebih panjang dipotong dengan **overlap 100 token**.
- **Baris tabel tidak pernah dipisah**, agar pasangan kegiatan–tanggal atau syarat–nilai tetap utuh dalam satu chunk.
- Judul bagian terdekat (mis. "Pasal 31", "BAB II") disimpan sebagai *heading* untuk membantu pencarian.

### 3. Embedding dan vector database

- Setiap chunk diubah menjadi vektor dengan `text-embedding-3-small` (1536 dimensi), dikirim dalam batch.
- Vektor disimpan di **ChromaDB** lokal dengan jarak cosine, bersama metadata `version_id` dan halaman. Pencarian hanya dilakukan pada versi dokumen yang sedang aktif.

### 4. Retrieval (hybrid search)

1. **Penulisan ulang kueri oleh GPT-6 Luna** (hanya bila perlu: pertanyaan lanjutan, menyebut halaman, sangat pendek, atau memuat kata yang tidak ada di dokumen; pertanyaan yang sudah jelas langsung dicari agar tetap cepat): pesan pengguna (bahasa santai, salah ketik seperti "sarat", singkatan, atau pertanyaan lanjutan seperti "lah di halaman 9 ga ada?") lebih dulu diubah menjadi kueri pencarian baku yang berdiri sendiri, beserta dokumen dan nomor halaman yang dimaksud. Kueri ini hanya dipakai untuk pencarian; jawaban tetap disusun dari pertanyaan asli pengguna. Pencarian memakai kueri baru **dan** pertanyaan asli sekaligus, sehingga penulisan ulang hanya menambah bukti, tidak menghilangkannya. Jika langkah ini gagal, pencarian memakai pertanyaan asli.
2. Kueri diubah menjadi embedding.
3. **Pencarian vektor**: 36 kandidat terdekat dari Chroma; kandidat dengan jarak cosine > 0,85 dibuang.
4. **Pencarian kata (BM25)** pada seluruh chunk aktif, dengan normalisasi variasi kata seperti *lulus/lolos/kelulusan* dan *syarat/persyaratan*.
5. Hasil keduanya digabung dengan *reciprocal rank fusion*. Tiga hasil teratas pencarian kata selalu disertakan agar bukti yang tepat secara kata tidak kalah dari kemiripan makna.
6. **Lanjutan halaman**: jika potongan teratas berakhir dengan kata sambung halaman (misalnya "1) Ijazah ....."), potongan pertama halaman berikutnya ikut dikirim agar daftar atau tabel yang terbelah tidak terpotong. Halaman yang disebut pengguna ("halaman 8 dan 9") hanya diprioritaskan pada dokumen yang sedang dibahas.
7. Maksimal **10 sumber / 24.000 karakter** dikirim ke LLM sebagai sumber bernomor `[S1]`, `[S2]`, dst.

### 5. Generasi jawaban (LLM)

GPT-6 Luna menerima pertanyaan, riwayat singkat, dan sumber bernomor dalam format JSON, lalu menjawab secara streaming. Prompt sistem lengkap ada di [`worker/src/policy.ts`](worker/src/policy.ts) (`ANSWER_SYSTEM`).

### Cara meminimalkan halusinasi

- **Hanya dari sumber**: prompt mewajibkan setiap fakta berasal dari sumber yang diberikan; riwayat percakapan bukan sumber fakta.
- **Balasan baku yang ramah untuk pertanyaan di luar dokumen**: jika informasi tidak ada di knowledge base, SIRA menampilkan kalimat tetap (bukan buatan model) yang menjelaskan bahwa SIRA hanya menjawab berdasarkan dokumen dan menyebut dokumen yang tersedia. Jawaban dari pengetahuan umum tidak lolos meskipun disertai catatan "tidak ada di dokumen".
- **Jawaban statis tanpa AI** ketika knowledge base kosong atau tidak ada kandidat relevan.
- **Teks ditahan sampai bersumber**: jawaban baru tampil di layar setelah memuat penanda sumber yang valid. Draf tanpa sumber (misalnya jawaban dari pengetahuan umum model) diperiksa dulu dan tidak pernah sempat terlihat; yang tampil hanya teks bersumber atau pernyataan bahwa informasi tidak ditemukan.
- **Wajib sitasi**: setiap pernyataan faktual harus diberi penanda `[S#]`. Backend memvalidasi bahwa ID yang dipakai benar-benar ada. Jawaban faktual tanpa sitasi diulang satu kali; jika tetap tanpa sitasi, jawaban ditandai gagal.
- **Pemeriksaan ulang terbatas**: jika model menyatakan informasi tidak ditemukan, backend melakukan satu pencarian tambahan dan memeriksa ulang bila ada sumber baru.
- **Aturan tabel dan daftar**: nilai harus diambil dari baris tabel yang sama; daftar persyaratan tidak boleh diklaim lengkap jika konteks hanya sebagian.
- **Pemisahan sumber**: setiap chunk membawa judul dokumen dan halaman, sehingga sumber Perpol dan SBP tidak tercampur tanpa terlihat.
- **Temperature rendah (0.1)** dan **proteksi prompt injection**: isi dokumen dan pertanyaan diperlakukan sebagai data, bukan instruksi; model tidak memiliki tool atau akses admin.

### Cara memberikan sumber jawaban

Model hanya menulis penanda `[S1]`, `[S2]`. Backend menerjemahkan penanda tersebut menjadi **judul dokumen dan nomor halaman** dari metadata database, sehingga model tidak dapat mengarang judul atau halaman. Referensi ditampilkan sebagai teks biasa di bawah jawaban.

## Instalasi

### Kebutuhan

- Windows 64-bit dengan PowerShell
- **Python 3.12 (64-bit)** — versi ini wajib karena seluruh dependensi dikunci dan diuji di 3.12. Python versi lain (3.13, 3.14, dst.) boleh tetap terpasang berdampingan; setup otomatis memilih 3.12.
- **Node.js 24 LTS** — untuk membangun tampilan web.
- Koneksi internet (instalasi dan pemanggilan AI). Ekstraksi PDF, OCR lokal, dan pencarian vektor berjalan di PC.
- Opsional: Tesseract OCR (`ind` + `eng`), hanya untuk meng-upload PDF hasil scan. Dipasang oleh `scripts/setup-ocr.ps1`.

Penguji **tidak** memerlukan akun Cloudflare, API key OpenAI, atau token manual selama masa akses demo aktif.

### Langkah instalasi

1. **Pastikan Python 3.12 tersedia.** Jalankan `py -0p` di PowerShell. Jika tidak ada baris `3.12`, unduh *Windows installer (64-bit)* Python 3.12 (misalnya 3.12.10) dari <https://www.python.org/downloads/windows/>, pasang dengan pengaturan bawaan, lalu buka ulang PowerShell. Python lain yang sudah ada tidak perlu dihapus.
2. **Pastikan Node.js 24 tersedia:** `node --version` harus `v24.x` (unduh di <https://nodejs.org/>).
3. Ekstrak/clone source, lalu buka PowerShell di folder yang berisi `setup.ps1` dan jalankan:

   ```powershell
   .\setup.ps1
   .\start.ps1
   ```

   `setup.ps1` mencari Python 3.12 secara otomatis (`python`, lalu `py -3.12`, lalu lokasi instalasi standar). Jika tidak ditemukan, setup berhenti dengan petunjuk pemasangan.

4. **Opsional — OCR untuk PDF hasil scan.** Lewati langkah ini jika hanya ingin mencoba tanya-jawab dengan dokumen bawaan atau meng-upload PDF teks biasa:

   ```powershell
   .\scripts\setup-ocr.ps1
   ```

5. Buka aplikasi:
   - Chat: <http://127.0.0.1:8000>
   - Admin: <http://127.0.0.1:8000/admin>
   - Swagger: <http://127.0.0.1:8000/docs>

`setup.ps1` membuat virtual environment `.venv`, memasang dependensi (versi terkunci), membangun frontend, menyiapkan tokenizer, meminta pembuatan akun admin, dan mengisi koneksi AI otomatis.

### Knowledge base bawaan

Saat aplikasi pertama kali dijalankan pada folder `data/` yang masih kosong, SIRA memuat paket `seed/knowledge.json.gz` (±0,7 MB): teks per halaman yang sudah diverifikasi, potongan teks (chunk), dan embedding Perpol 1/2025 (71 halaman) serta Pengumuman SBP T.A. 2027 (12 halaman). Tidak ada OCR, embedding ulang, atau request AI saat memuatnya.

- **File PDF tidak disertakan** di repository. Karena itu, untuk dua dokumen bawaan, fitur yang membutuhkan PDF asli (**Review dan koreksi** dengan gambar halaman dan **Baca ulang dengan AI**) baru aktif setelah admin memakai **Ganti file** untuk mengunggah PDF-nya. Ubah judul, hapus, dan tanya-jawab berjalan normal.
- Paket hanya dimuat **sekali**. Jika admin menghapus atau mengganti dokumen bawaan, dokumen tersebut tidak muncul kembali setelah restart. Instalasi yang sudah memiliki dokumen tidak diubah.
- Untuk memulai dengan knowledge base kosong, isi `SIRA_SEED_KB=false` di `.env` sebelum menjalankan aplikasi pertama kali.
- Memperbarui paket dari knowledge base yang sedang aktif (hentikan backend dahulu): `.\.venv\Scripts\python.exe scripts\export-seed.py`.

### Membuat akun admin

Penguji membuat username dan password sendiri saat `setup.ps1` berjalan. **Tidak ada password bawaan.**

1. **Nama admin [admin]:** isi nama pengguna, atau tekan Enter untuk `admin`.
2. **Password (minimal 12 karakter):** karakter tidak terlihat saat diketik; ini normal.
3. **Ulangi password.**

Akun hanya berlaku pada instalasi di komputer tersebut dan disimpan sebagai hash Argon2 di folder `data/` (tidak masuk Git). Menjalankan setup ulang tidak mengganti password. Untuk reset, hentikan aplikasi lalu jalankan:

```powershell
.\.venv\Scripts\python.exe -m backend.setup_admin --reset
```

### Koneksi AI

`setup.ps1` (dan `start.ps1` bila belum terisi) mengambil konfigurasi demo dari endpoint Cloudflare di `config/relay.json`, lalu menyimpan URL dan token demo di `.env` lokal. Konfigurasi milik pengguna yang sudah lengkap tidak ditimpa. Setelah aplikasi berjalan, login admin lalu klik **Uji koneksi AI** (satu request embedding kecil).

- Akses demo berlaku sampai **30 Oktober 2026 pukul 23.59 WIB**. Setelah itu pemanggilan AI berhenti, tetapi dokumen dan data lokal tetap tersimpan.
- Pemakaian AI selama masa demo ditagihkan ke akun pemilik. **API key OpenAI tidak pernah dikirim ke komputer penguji**; token demo dibatasi model, operasi, kecepatan, dan masa berlaku oleh relay. Jangan membagikan `.env`.
- Panduan detail: [instalasi otomatis](docs/automatic-installation.md) · [relay milik sendiri / konfigurasi manual](docs/relay-setup.md).

### Jika Python 3.12 berada di lokasi lain

Setup biasanya menemukan Python 3.12 sendiri. Jika Python 3.12 dipasang di lokasi yang tidak standar, tunjuk langsung executable-nya:

```powershell
.\setup.ps1 -PythonPath 'C:\lokasi\Python312\python.exe'   # ganti dengan lokasi Python 3.12 Anda
```

### Jika PowerShell memblokir skrip

Hanya jika muncul pesan seperti `running scripts is disabled`, jalankan perintah berikut lalu ulangi skrip pada jendela yang sama:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

`-Scope Process` hanya berlaku untuk jendela PowerShell tersebut dan tidak mengubah kebijakan permanen. Lihat [dokumentasi Microsoft](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies/).

### Catatan menjalankan

- Gunakan alamat `127.0.0.1` secara konsisten agar cookie dan pemeriksaan origin sesuai.
- Port lain: `.\start.ps1 -Port 8001`. Jalankan satu proses backend saja (tanpa `--workers`).
- Tesseract milik sendiri dapat dipakai dengan mengisi `SIRA_TESSERACT_CMD` di `.env`.

## Penggunaan

1. Login ke `/admin`, klik **Uji koneksi AI**. Dua dokumen bawaan sudah berstatus **siap**.
2. Untuk menambah dokumen, upload PDF dengan judul yang jelas, tunggu status **siap**. PDF teks selesai dalam hitungan detik; PDF scan membutuhkan waktu OCR dan bantuan AI.
3. Jika ada halaman yang perlu diperiksa, buka **Review dan koreksi**: cocokkan teks dengan gambar asli, perbaiki, konfirmasi, lalu klik **Buat indeks dari hasil review**. Detail: [review dokumen aktif](docs/active-document-review.md).
4. Buka halaman chat dan ajukan pertanyaan, misalnya:
   - "Bagaimana ketentuan penilaian kinerja anggota Polri?"
   - "Apa saja persyaratan mengikuti SBP T.A. 2027?"
5. Judul dapat diubah tanpa embedding ulang. Mengganti file membuat versi baru; versi lama tetap aktif jika penggantian gagal.

Panduan demonstrasi: [docs/demo.md](docs/demo.md).

## Dokumentasi API

- **File OpenAPI 3.1:** [`docs/openapi.json`](docs/openapi.json) — dapat dibuka tanpa menjalankan aplikasi, misalnya di [Swagger Editor](https://editor.swagger.io/) (File → Import file) atau di **Postman** (Import → pilih file, otomatis menjadi collection dengan base URL `http://127.0.0.1:8000`).
- **Swagger UI interaktif:** <http://127.0.0.1:8000/docs> saat aplikasi berjalan.
- Memperbarui file setelah API berubah: `.\.venv\Scripts\python.exe scripts\export-openapi.py` (tanpa menjalankan server atau memanggil AI).

Endpoint admin memerlukan login: cookie sesi `HttpOnly` dan header `X-CSRF-Token` untuk request yang mengubah data.

| Method | Endpoint | Fungsi |
| --- | --- | --- |
| GET | `/api/health` | Status aplikasi |
| POST | `/api/admin/login` · `/api/admin/logout` | Login / logout admin |
| GET | `/api/admin/me` | Info sesi admin |
| POST | `/api/admin/check-ai` | Uji koneksi AI |
| GET | `/api/admin/documents` | Daftar dokumen dan status |
| POST | `/api/admin/documents` | Upload dokumen baru |
| PATCH | `/api/admin/documents/{id}` | Ubah judul |
| PUT | `/api/admin/documents/{id}/file` | Ganti file (versi baru) |
| DELETE | `/api/admin/documents/{id}` | Hapus dokumen |
| POST | `/api/admin/documents/{id}/retry` | Proses ulang dokumen gagal |
| POST | `/api/admin/documents/{id}/read-ai` | Baca ulang dengan AI |
| POST · GET | `/api/admin/documents/{id}/review` | Mulai / lihat draft review |
| GET | `/api/admin/documents/{id}/review/pages/{n}/image` | Gambar halaman untuk review |
| PUT | `/api/admin/documents/{id}/review/pages/{n}` | Simpan koreksi halaman |
| POST | `/api/admin/documents/{id}/review/activate` | Buat indeks dari hasil review |
| POST | `/api/chat/sessions` | Buat sesi / percakapan baru |
| POST | `/api/chat/history` | Ambil riwayat percakapan |
| POST | `/api/chat` | Kirim pertanyaan, jawaban streaming |

## Struktur proyek dan database

```text
backend/app/      API FastAPI, autentikasi, ingestion, OCR, retrieval, chat
  main.py           routing REST API
  ingestion.py      validasi, ekstraksi, chunking, embedding
  ocr_pipeline.py   OCR lokal + AI
  native_pdf.py     ekstraksi tabel PDF teks
  retrieval.py      pencarian kata BM25 dan penggabungan hasil
  chat.py           sesi, retrieval, prompt, validasi sitasi
  vectors.py        ChromaDB
  db.py             skema SQLite
  seed.py           memuat knowledge base bawaan sekali pada instalasi kosong
seed/             knowledge base bawaan (teks, chunk, embedding; tanpa PDF)
frontend/src/     UI React (chat dan admin)
worker/src/       Relay Cloudflare: prompt (policy.ts), kuota, pembatasan model
tests/            Tes backend (AI tiruan)
worker/test/      Tes relay
scripts/          Setup OCR, konfigurasi relay, ekspor OpenAPI dan knowledge base bawaan
docs/             Dokumentasi teknis dan catatan pengujian
data/             SQLite, PDF, Chroma, cache tokenizer (lokal, tidak masuk Git)
```

### Tabel SQLite utama

| Tabel | Isi |
| --- | --- |
| `admin`, `admin_sessions` | Akun admin (hash Argon2) dan sesi login (hash token + CSRF) |
| `documents` | Judul, nama file, versi aktif dan versi yang sedang diproses |
| `versions` | File per versi: hash SHA-256, ukuran, status, progres, jumlah halaman, pesan error |
| `pages` | Teks per halaman dan metode ekstraksinya |
| `chunks` | Potongan teks yang diindeks: versi, halaman, heading |
| `review_pages`, `ocr_regions`, `ocr_page_jobs` | Draft review manual dan checkpoint OCR per area/halaman |
| `chat_sessions`, `chat_messages` | Sesi chat (hash token), konteks pertanyaan, dan riwayat pesan |

Browser hanya menyimpan token sesi acak (localStorage dan cookie HttpOnly sebagai cadangan); backend menyimpan hash-nya saja. PDF dan database tidak dilayani sebagai file web. Hentikan backend sebelum menyalin folder `data/` untuk backup.

## Pengujian

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check backend tests scripts
cd frontend; npm ci; npm run build
cd ..\worker; npm ci; npm run check; npm test; npm run dry-run; npm run test:runtime
```

Seluruh tes memakai AI tiruan dan kredensial palsu, sehingga tidak menagih OpenAI. `test:runtime` membutuhkan hasil `npm run dry-run` terbaru. Hasil dan batas verifikasi dicatat di [docs/testing.md](docs/testing.md).

## Keterbatasan dan pengembangan lanjutan

**Keterbatasan**

- Membutuhkan internet dan layanan OpenAI untuk embedding, OCR AI, dan jawaban.
- Kualitas OCR dokumen scan tidak dijamin 100%; angka, tanggal, dan negasi tetap perlu dicek melalui Review dan koreksi.
- Proteksi prompt injection mengurangi risiko, tetapi tidak menjamin kebal terhadap semua jailbreak.
- Validasi sitasi memastikan ID sumber valid, bukan memeriksa dukungan makna setiap kalimat.
- Semua dokumen aktif dapat menjadi bahan jawaban; belum ada klasifikasi kerahasiaan atau hak akses per pengguna.
- Satu admin, satu percakapan per browser, satu proses backend. Hanya format PDF.
- Diuji pada Windows pengembang; instalasi pada PC Windows bersih belum diverifikasi.

**Pengembangan lanjutan**

- Pilihan model/provider AI dan pengaturan API key melalui admin.
- Klasifikasi dokumen dan hak akses per pengguna; banyak akun dan admin.
- Daftar beberapa percakapan dan sinkronisasi riwayat antarperangkat.
- Format dokumen lain (DOCX, gambar), deployment penuh ke cloud.
- Evaluasi otomatis akurasi retrieval dan jawaban dengan set pertanyaan acuan.

## Troubleshooting

| Masalah | Langkah |
| --- | --- |
| "Python 3.12 (64-bit) belum ditemukan" | Pasang Python 3.12 64-bit (langkah 1 instalasi), buka ulang PowerShell, lalu jalankan ulang `.\setup.ps1`. Jika sudah terpasang di lokasi lain: `.\setup.ps1 -PythonPath <lokasi python.exe>` |
| "Folder .venv sudah ada tetapi bukan Python 3.12" | Hapus folder `.venv` (dibuat dari Python versi lain), lalu jalankan ulang `.\setup.ps1` |
| `SyntaxError` lalu `Unduhan tabel tokenizer gagal` | Gunakan `setup.ps1` terbaru, lalu ulangi setup. Tidak perlu menghapus `.venv` atau `.env` |
| Koneksi AI otomatis gagal | Periksa internet dan masa akses demo, jalankan `.\.venv\Scripts\python.exe -m backend.setup_relay`, lalu restart |
| Relay menolak akses | Token, masa berlaku, atau kuota relay perlu diperiksa pemilik relay |
| OCR tidak tersedia saat upload PDF scan | Jalankan `.\scripts\setup-ocr.ps1` (opsional, hanya untuk PDF scan) atau periksa `tesseract --list-langs` |
| Hasil OCR salah pada angka/negasi | Gunakan **Review dan koreksi**, atau **Baca dengan AI** |
| Login/CSRF gagal | Buka lewat `http://127.0.0.1:8000` (atau port pilihan `start.ps1`), lalu login ulang |
| Pemrosesan terputus | Restart aplikasi, login admin, pilih **Proses ulang**; versi lama yang siap tetap tersedia |
| Frontend belum dibangun | Jalankan `npm ci` lalu `npm run build` di folder `frontend/` |

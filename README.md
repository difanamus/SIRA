# SIRA — Asisten Informasi SDM Polri

Prototype RAG untuk menjawab pertanyaan berdasarkan PDF yang dimasukkan admin. Instalasi baru dimulai dengan knowledge base kosong. PDF, teks hasil ekstraksi, metadata, dan indeks disimpan persisten pada komputer yang menjalankan aplikasi.

Halaman chat berada di `/`, halaman pengelolaan dokumen di `/admin`. Referensi jawaban berupa nama dokumen dan halaman, tanpa tautan atau unduhan PDF. Riwayat dan konteks percakapan tetap tersedia setelah refresh, tutup/buka browser yang sama, dan restart aplikasi. Hanya **Percakapan baru** yang menghapus sesi lama dan memulai percakapan kosong.

## Kebutuhan

- Windows 64-bit, Python **3.12**, Node.js **24 LTS**, dan PowerShell.
- Internet untuk instalasi dan pemanggilan AI. Ekstraksi PDF, OCR lokal, dan pencarian vektor berjalan di PC.
- Relay Cloudflare milik peserta yang telah dikonfigurasi. Penguji tidak perlu akun Cloudflare, Wrangler, atau API key OpenAI.
- Tesseract dengan bahasa `ind` dan `eng` untuk PDF scan.

Dependensi Python dan npm dikunci. Implementasi diuji pada lingkungan Windows pengembang; pengujian instalasi pada PC Windows bersih masih perlu dilakukan.

## Instalasi dan menjalankan

Jalankan PowerShell di folder proyek:

```powershell
.\setup.ps1 -PythonPath 'C:\path\ke\Python312\python.exe'
.\scripts\setup-ocr.ps1
.\start.ps1
```

`setup.ps1` membuat `.venv`, memasang dependensi, membangun frontend, menyiapkan tokenizer, dan meminta akun admin melalui terminal. Password minimal 12 karakter, disimpan sebagai hash Argon2. Jika PowerShell memblokir skrip, jalankan skrip dengan `pwsh -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1 -PythonPath 'C:\path\ke\python.exe'` untuk proses tersebut.

OCR dipasang lokal dalam `tools/tesseract`, dengan checksum installer dan model bahasa yang diverifikasi. Skrip tidak menghapus instalasi yang sudah ada. Alternatif: isi `SIRA_TESSERACT_CMD` di `.env` dengan path Tesseract milik Anda, pastikan model `ind` dan `eng` tersedia.

Konfigurasi AI tersimpan pada `.env` lokal, berdasarkan `.env.example`. Isi `SIRA_RELAY_URL` dan `SIRA_RELAY_TOKEN` dengan akses relay pengujian yang diberikan peserta. **Jangan menaruh API key OpenAI di frontend atau membagikan `.env` melalui Git.** Petunjuk untuk pemilik relay ada pada [docs/relay-setup.md](docs/relay-setup.md).

Buka:

- Chat: <http://127.0.0.1:8000>
- Admin: <http://127.0.0.1:8000/admin>
- Swagger/OpenAPI: <http://127.0.0.1:8000/docs>

Gunakan alamat `127.0.0.1` yang sama secara konsisten agar pemeriksaan origin, cookie, dan penyimpanan penanda percakapan sesuai. `start.ps1 -Port 8001` memilih port lain sekaligus menyesuaikan origin. Jalankan satu proses backend, tanpa `--workers` tambahan; penguncian chat dan antrean ingestion berada di memori proses, sedangkan riwayat serta konteks chat disimpan di SQLite.

## Penggunaan

1. Login admin, lalu pilih **Uji koneksi AI**. Status konfigurasi di UI belum membuktikan OpenAI dapat dihubungi; tombol ini melakukan satu request embedding kecil yang berbiaya.
2. Upload PDF dengan judul yang jelas. Batas 100 MiB dan 300 halaman secara default. PDF terenkripsi, rusak, dan non-PDF ditolak.
3. Tunggu status siap. Pemrosesan berjalan di background dengan progres. PDF scan membutuhkan waktu OCR dan mungkin bantuan vision.
   Scan memakai **OCR lokal → GPT-4.1 mini → GPT-5.6 Sol**. AI mini memeriksa bagian yang meragukan; pembacaan kedua dilakukan jika hasil berbeda atau ragu. Sol hanya menerima potongan terkait, maksimal dua potongan per halaman, tanpa menerima seluruh halaman maupun transkripsi sebelumnya. Jika gagal, **Baca dengan AI** meminta pemeriksaan mini pada semua potongan nonkosong, tetap setelah OCR lokal. Bantuan AI berbayar; chatbot tetap GPT-4o mini. Hasil setiap tahap tersimpan agar retry tidak mengulang request yang sudah berhasil. Gangguan jaringan/kuota berhenti tanpa eskalasi ke model lebih mahal.
   Alternatif: pilih **Review dan koreksi**. Sistem menyiapkan teks secara lokal, mempertahankan halaman hasil AI yang sudah tersedia, lalu menampilkan gambar asli dan editor per halaman. Pilih potongan yang ditandai, cocokkan dengan gambar, koreksi teks, dan simpan konfirmasi. Halaman yang sudah lolos otomatis tidak wajib dikonfirmasi ulang. Edit tambahan pada halaman otomatis membuat halaman itu memerlukan konfirmasi. Halaman kosong memerlukan penandaan eksplisit. Setelah halaman yang perlu review dikonfirmasi, pilih **Buat indeks dari hasil review**. Langkah terakhir hanya memakai embedding, tanpa OCR AI ulang. Draft tetap tersimpan setelah refresh/restart; versi lama tetap aktif hingga indeks baru berhasil.
4. Ajukan pertanyaan di chat. Pertanyaan lanjutan menggunakan maksud pertanyaan sebelumnya dan retrieval baru. SIRA meminta klarifikasi jika konteks belum cukup.
5. Ubah judul tanpa embedding ulang, ganti PDF melalui versi baru, atau hapus melalui admin. Versi lama tetap aktif jika penggantian gagal. Pekerjaan yang terputus ditandai gagal saat startup dan dapat diproses ulang.

Jika belum ada dokumen atau evidence tidak cukup, SIRA memberi pemberitahuan yang sopan. Kesalahan AI dan jawaban streaming yang terputus ditandai jelas. Jawaban tanpa referensi valid tidak ditandai selesai.

## Arsitektur

```text
Browser → FastAPI lokal → Cloudflare relay → OpenAI
              ↓
      SQLite + PDF + Chroma lokal
```

Ingestion: validasi PDF → ekstraksi teks per halaman → OCR lokal jika perlu → GPT-4.1 mini → GPT-5.6 Sol hanya pada potongan meragukan → review selektif jika belum lolos → chunk maksimal sekitar 650 token → embedding `text-embedding-3-small` → indeks Chroma → aktivasi versi.

Chat: pertanyaan dan konteks maksud sesi → embedding query → pencarian versi aktif → evidence bernomor → GPT-4o mini → streaming → validasi ID sumber → referensi teks. Histori jawaban model tidak dijadikan sumber fakta.

API key OpenAI hanya berada di Cloudflare Secrets. Relay membatasi operasi, model, payload, jumlah request, unit reservasi, kecepatan, dan masa berlaku. Token lokal dapat dicabut. Pengguna dengan kendali penuh atas PC dapat membaca token relay lokal, sehingga token tersebut memiliki batas penggunaan dan bukan API key utama.

## Struktur dan penyimpanan

| Lokasi | Isi |
| --- | --- |
| `backend/app/` | API, autentikasi, OCR, ingestion, retrieval, streaming |
| `frontend/src/` | Chat dan admin React/TypeScript |
| `worker/src/` | Relay OpenAI dan kuota persisten Durable Object |
| `tests/`, `worker/test/` | Pengujian lokal dengan AI tiruan |
| `data/` | SQLite, PDF, indeks Chroma, cache tokenizer; tidak dilacak Git |
| `docs/` | Setup relay, bukti uji, dan panduan demo |

Hentikan backend sebelum menyalin seluruh `data/` untuk backup. PDF dan database tidak dilayani sebagai aset web. Pesan, referensi, status jawaban, dan konteks chat disimpan di SQLite; browser menyimpan token sesi acak di localStorage. Backend hanya menyimpan hash token. Membuka riwayat tidak memanggil OpenAI. Browser/profil berbeda memulai percakapan terpisah; menghapus data situs atau memakai alamat/port lain membuat penanda sesi tidak tersedia. **Percakapan baru** menghapus pesan/konteks sesi lama dan mencabut token lamanya. Riwayat jawaban lama hanya untuk tampilan, bukan sumber fakta bagi model. Untuk mereset password admin, hentikan aplikasi lalu jalankan:

```powershell
.\.venv\Scripts\python.exe -m backend.setup_admin --reset
```

## Pengujian

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check backend tests scripts
cd frontend
npm ci
npm run build
cd ..\worker
npm ci
npm run check
npm test
npm run dry-run
npm run test:runtime
```

Runtime test memerlukan hasil bundel `worker/dist/index.js`; seluruh tes memakai kredensial palsu dan tidak menagih OpenAI. Hasil serta batas verifikasi nyata dicatat pada [docs/testing.md](docs/testing.md). Panduan demonstrasi dan video ada di [docs/demo.md](docs/demo.md).

## Batas prototype

- Proteksi prompt injection berlapis mengurangi risiko; hasil uji tidak menjamin model kebal terhadap semua jailbreak.
- Seluruh dokumen aktif dapat menjadi bahan jawaban. Referensi tanpa tautan tidak menerapkan klasifikasi kerahasiaan atau hak akses isi.
- OCR membagi halaman menjadi enam potongan tanpa overlap di sela baris atau batas penuh tabel. Satu potongan maksimal 25% tinggi halaman; sel gabungan dijaga melalui deteksi garis tabel. Jika pembagian aman tidak ditemukan, gunakan review manual. Sol hanya untuk potongan yang masih tidak konsisten setelah mini, maksimal dua potongan per halaman. Hasil Sol harus terbaca dan cocok dengan salah satu pembacaan mini; hasil yang tetap berbeda ditandai untuk review. Confidence tinggi maupun kesepakatan model bukan jaminan benar. Sol adalah fallback OCR, bukan model jawaban chat.
- Pemilihan provider/model, klasifikasi dokumen, banyak admin, daftar beberapa percakapan, sinkronisasi riwayat antarperangkat, dan deployment aplikasi penuh ke cloud merupakan pengembangan lanjutan.
- Ambang retrieval, kelengkapan jawaban tabel/rumus, kualitas OCR, serta latency OpenAI perlu dievaluasi menggunakan dokumen dan koneksi nyata.
- Jawaban faktual tanpa referensi memicu satu pengulangan terbatas. Draft diganti di UI; jika masih tanpa referensi, jawaban ditandai gagal. Ini dapat menambah waktu pada kasus tersebut.

## Troubleshooting

| Masalah | Langkah |
| --- | --- |
| AI belum dikonfigurasi | Isi relay URL/token pada `.env`, restart backend, uji koneksi dari admin |
| Relay menolak akses | Periksa token, aktivasi, tanggal kedaluwarsa, dan kuota melalui pemilik relay |
| OCR tidak tersedia | Jalankan setup OCR atau periksa path dan `tesseract --list-langs` |
| Ingestion gagal pada angka/negasi | Gunakan Review dan koreksi untuk mencocokkan gambar serta memperbaiki teks; atau Baca dengan AI jika kuota tersedia |
| Kuota total relay tidak cukup | Review lokal tetap dapat disiapkan. Penambahan kuota OCR membutuhkan keputusan pemilik layanan; menunggu tidak mereset batas total. Indeks tetap memerlukan kuota embedding |
| Login/CSRF gagal | Gunakan `http://127.0.0.1:8000` atau port yang dipilih `start.ps1`, login ulang |
| Pemrosesan terputus | Restart, login admin, pilih proses ulang; versi lama yang siap tetap tersedia |
| Frontend belum dibangun | Jalankan `npm ci` lalu `npm run build` dalam `frontend/` |

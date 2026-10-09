# SIRA — Sistem Informasi dan Referensi Aparatur

Asisten Informasi SDM Polri berbasis dokumen. Nama SIRA merupakan singkatan dari **Sistem Informasi dan Referensi Aparatur**.

Prototype RAG untuk menjawab pertanyaan berdasarkan PDF yang dimasukkan admin. Instalasi baru dimulai dengan knowledge base kosong. PDF, teks hasil ekstraksi, metadata, dan indeks disimpan persisten pada komputer yang menjalankan aplikasi.

Halaman chat berada di `/`, halaman pengelolaan dokumen di `/admin`. Referensi jawaban berupa nama dokumen dan halaman, tanpa tautan atau unduhan PDF. Riwayat dan konteks percakapan tetap tersedia setelah refresh, tutup/buka browser yang sama, dan restart aplikasi. Hanya **Percakapan baru** yang menghapus sesi lama dan memulai percakapan kosong.

SIRA menjawab sapaan dan pertanyaan perkenalan seperti “kamu siapa?”, “SIRA itu apa?”, dan “oy SIRA” secara sopan tanpa request AI, termasuk saat knowledge base masih kosong. Perkenalan tidak mengganti konteks pertanyaan dokumen. Jalur ini hanya menerima pesan lengkap yang cocok dengan pola perkenalan; pesan yang juga memuat pertanyaan dokumen atau instruksi lain tetap mengikuti alur RAG dan pemeriksaan yang sudah ada.

PDF teks dengan tabel dibaca melalui posisi karakter dan batas sel asli, termasuk sel gabungan. Tabel tidak otomatis memerlukan AI atau review manual. Jika struktur native belum lengkap, bagian bermasalah tetap diperiksa lewat gambar asli. PDF scan tetap mengikuti OCR lokal → GPT-4.1 mini → GPT-5.6 Sol → review selektif jika belum lolos. **Proses ulang** dapat melanjutkan dokumen gagal yang sempat dibuka untuk review; koreksi manusia tetap disimpan. Detail: [ekstraksi tabel native](docs/native-pdf-tables.md).

## Kebutuhan

- Windows 64-bit, Python **3.12**, Node.js **24 LTS**, dan PowerShell.
- Internet untuk instalasi dan pemanggilan AI. Ekstraksi PDF, OCR lokal, dan pencarian vektor berjalan di PC.
- Relay Cloudflare milik peserta. Selama akses demo ujian aktif, instalasi terhubung otomatis; penguji tidak perlu akun Cloudflare, Wrangler, API key OpenAI, atau memasukkan token secara manual.
- Tesseract dengan bahasa `ind` dan `eng` untuk PDF scan.

Dependensi Python dan npm dikunci. Implementasi diuji pada lingkungan Windows pengembang; pengujian instalasi pada PC Windows bersih masih perlu dilakukan.

## Instalasi dan menjalankan

Ekstrak/unduh source ke folder proyek, lalu buka PowerShell di folder yang berisi `setup.ps1`. Periksa versi:

```powershell
python --version
node --version
```

Jika `python` menunjuk **Python 3.12.x** dan Node menunjukkan **v24.x**, jalankan:

```powershell
.\setup.ps1
.\scripts\setup-ocr.ps1
.\start.ps1
```

`setup.ps1` membuat `.venv`, memasang dependensi, membangun frontend, menyiapkan tokenizer, dan meminta Anda membuat akun admin melalui terminal. Setup juga mengisi koneksi Cloudflare otomatis selama masa akses demo aktif.

### Jika komputer memiliki beberapa versi Python

`-PythonPath` adalah **lokasi executable Python 3.12 pada komputer yang sedang memasang SIRA**. Path ini bukan lokasi Bypass dan tidak harus sama dengan komputer peserta. Jika launcher `py` dan Python 3.12 sudah terpasang, tampilkan lokasinya dengan:

```powershell
py -3.12 -c "import sys; print(sys.executable)"
```

Salin lokasi yang ditampilkan, lalu gunakan untuk setup. Contoh berikut adalah placeholder; **ganti dengan lokasi yang benar pada laptop Anda**:

```powershell
$python312 = 'C:\lokasi\Python312\python.exe'
& $python312 --version
.\setup.ps1 -PythonPath $python312
```

Pastikan pemeriksaan versi menghasilkan `Python 3.12.x`. Jika launcher tidak menemukan Python 3.12, pasang Python 3.12 terlebih dahulu atau gunakan lokasi instalasi 3.12 yang memang tersedia. Setelah setup selesai, lanjutkan skrip OCR dan `start.ps1` seperti di atas. Path khusus runtime Codex pada komputer peserta tidak diperlukan pada laptop penguji.

### Hanya jika PowerShell memblokir skrip

**Bypass bukan langkah instalasi wajib.** Jalankan skrip biasa terlebih dahulu. Jika muncul pesan seperti `running scripts is disabled` atau skrip diblokir oleh execution policy, dan kebijakan komputer Anda mengizinkannya, jalankan:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Setujui konfirmasi, kemudian jalankan kembali skrip setup/OCR/start pada jendela PowerShell yang sama. `Process` membuat perubahan berlaku pada sesi tersebut dan proses turunannya, tanpa mengubah kebijakan permanen; perubahan berakhir ketika sesi/proses itu ditutup. `-Force` hanya menghilangkan konfirmasi dan tidak diperlukan. Kebijakan organisasi melalui Group Policy tetap memiliki prioritas. Lihat [dokumentasi execution policy Microsoft](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies/).

Untuk mencoba instalasi baru sambil aplikasi lama tetap berjalan, gunakan folder source terpisah dan jalankan `.\start.ps1 -Port 8001`. Buka `http://127.0.0.1:8001/admin`; folder data dan akun instalasi baru terpisah, serta penguji tetap membuat akun admin sendiri.

### Membuat akun admin pada instalasi pertama

**Penguji membuat username dan password sendiri saat menjalankan `setup.ps1`. Tidak ada password admin bawaan yang perlu diperoleh dari peserta atau README.** Setelah pemasangan dependensi selesai, terminal akan meminta:

1. **Nama admin [admin]:** masukkan nama pengguna pilihan Anda, atau tekan Enter untuk menggunakan `admin`.
2. **Password (minimal 12 karakter):** masukkan password pilihan Anda. Karakter password tidak terlihat saat diketik di terminal; ini normal.
3. **Ulangi password:** ketik kembali password yang sama untuk konfirmasi.

Setelah akun dibuat, setup menghubungkan AI ke Cloudflare secara otomatis. Lanjutkan pemasangan OCR, lalu jalankan `.\start.ps1`. Buka <http://127.0.0.1:8000/admin> dan login menggunakan username serta password yang baru Anda buat. Simpan password secara pribadi; jangan memasukkannya ke README atau GitHub.

Akun ini hanya berlaku pada instalasi SIRA di komputer Anda. Orang lain yang mengunduh kode dan membuat akun pada instalasi mereka tidak otomatis mendapat akses ke instalasi Anda. Password disimpan sebagai hash Argon2 dalam database lokal di folder `data/`, yang tidak dilacak Git.

Jika akun sudah ada, menjalankan setup lagi tidak mengganti password. Gunakan akun sebelumnya; jika lupa password, ikuti perintah reset pada bagian **Struktur dan penyimpanan**. Pembuatan akun dan reset dilakukan melalui terminal pada komputer yang menjalankan SIRA, bukan melalui pendaftaran publik di halaman login.

### OCR dan konfigurasi AI

OCR dipasang lokal dalam `tools/tesseract`, dengan checksum installer dan model bahasa yang diverifikasi. Skrip tidak menghapus instalasi yang sudah ada. Alternatif: isi `SIRA_TESSERACT_CMD` di `.env` dengan path Tesseract milik Anda, pastikan model `ind` dan `eng` tersedia.

**Penguji tidak perlu mengisi konfigurasi AI secara manual.** `setup.ps1` mengambil konfigurasi demo dari endpoint Cloudflare yang tercantum dalam `config/relay.json`, lalu menyimpan URL dan token demo pada `.env` lokal. `start.ps1` juga menjalankan langkah ini apabila konfigurasi belum terisi. Konfigurasi milik pengguna yang sudah lengkap tidak ditimpa. Tidak ada request OpenAI saat mengambil konfigurasi; sesudah aplikasi berjalan, login admin dan pilih **Uji koneksi AI** untuk memeriksa OpenAI dengan satu request embedding kecil berbayar.

Akses demo ujian berlaku hingga **16 Oktober 2026 pukul 10.42 WIB** (batas tepat: `2026-10-16T03:42:55Z`). Setelah berakhir atau dicabut pemilik, pemanggilan AI berhenti; dokumen dan data lokal tetap tersimpan. Jika koneksi otomatis gagal, setup memberi pesan bahwa AI belum siap. Periksa internet, lalu ulangi setup atau jalankan `.\.venv\Scripts\python.exe -m backend.setup_relay`.

Pemilik telah mengizinkan akses demo publik selama masa pengujian: siapa pun yang mengunduh kode dapat memperoleh token demo melalui endpoint instalasi dan pemakaian AI ditagihkan ke akun pemilik. Token demo berbeda dari token privat instalasi pemilik; model, operasi, proteksi per menit, dan masa berlaku tetap dikendalikan Cloudflare. **API key OpenAI tidak dikirim ke laptop penguji. Jangan membagikan `.env` melalui Git.** Panduan aktivasi/pencabutan: [instalasi otomatis](docs/automatic-installation.md). Petunjuk relay milik sendiri dan konfigurasi manual sebagai alternatif ada pada [docs/relay-setup.md](docs/relay-setup.md).

Buka:

- Chat: <http://127.0.0.1:8000>
- Admin: <http://127.0.0.1:8000/admin>
- Swagger/OpenAPI: <http://127.0.0.1:8000/docs>

Gunakan alamat `127.0.0.1` yang sama secara konsisten agar pemeriksaan origin, cookie, dan penyimpanan penanda percakapan sesuai. `start.ps1 -Port 8001` memilih port lain sekaligus menyesuaikan origin. Jalankan satu proses backend, tanpa `--workers` tambahan; penguncian chat dan antrean ingestion berada di memori proses, sedangkan riwayat serta konteks chat disimpan di SQLite.

## Penggunaan

1. Login admin, lalu pilih **Uji koneksi AI**. Status konfigurasi di UI belum membuktikan OpenAI dapat dihubungi; tombol ini melakukan satu request embedding kecil yang berbiaya.
2. Upload PDF dengan judul yang jelas. Batas 100 MiB dan 300 halaman secara default. PDF terenkripsi, rusak, dan non-PDF ditolak.
3. Tunggu status siap. Pemrosesan berjalan di background dengan progres. PDF scan membutuhkan waktu OCR dan mungkin bantuan vision.
   Scan memakai **OCR lokal → GPT-4.1 mini → GPT-5.6 Sol**. Pemeriksaan lokal seluruh dokumen berjalan tanpa menunggu AI. Tiga worker AI membaca gambar asli secara mandiri, tanpa teks OCR/transkripsi model sebelumnya. Tabel dibaca utuh dengan struktur baris, kolom dan sel gabungan; Sol hanya membaca area yang belum lolos. Jika tetap ragu, tersedia review selektif manusia. **Baca dengan AI** meminta pembacaan gambar pada semua area nonkosong; pada dokumen siap, **Baca ulang dengan AI** membuat versi baru dari PDF tersimpan tanpa upload ulang. Bantuan AI berbayar; chatbot tetap GPT-4o mini. Checkpoint mencegah request berhasil diulang saat resume. Gangguan layanan menghentikan antrean AI berikutnya tanpa eskalasi model, sementara pemeriksaan lokal tetap berjalan.
   Alternatif: pilih **Review dan koreksi**. Sistem menyiapkan teks secara lokal, mempertahankan halaman hasil AI yang sudah tersedia, lalu menampilkan gambar asli dan editor per halaman. Petunjuk menampilkan alasan dan kutipan yang diragukan. Pilih **Lihat bagian ini dan tandai teks** untuk membuka crop gambar dan menyorot kutipan pada editor. Area perkiraan diberi label; jika AI gagal format dan lokasi kata belum diketahui, kegagalan tersebut dijelaskan secara terpisah. Cocokkan dengan gambar, koreksi teks, dan simpan konfirmasi. Halaman yang sudah lolos otomatis tidak wajib dikonfirmasi ulang. Edit tambahan pada halaman otomatis membuat halaman itu memerlukan konfirmasi. Halaman kosong memerlukan penandaan eksplisit. Setelah halaman yang perlu review dikonfirmasi, pilih **Buat indeks dari hasil review**. Langkah terakhir hanya memakai embedding, tanpa OCR AI ulang. Draft tetap tersimpan setelah refresh/restart; versi lama tetap aktif hingga indeks baru berhasil.
   Dokumen yang sudah siap juga tetap memiliki **Review dan koreksi**. Ringkasan admin menampilkan jumlah halaman aktif, indikator OCR lokal dari bukti tersimpan, dan rekomendasi review opsional. Skor ini bukan persentase kebenaran. Review membuka draft terpisah tanpa OCR/AI ulang; versi aktif tetap tersedia. Detail: [review dokumen aktif](docs/active-document-review.md).
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

Hentikan backend sebelum menyalin seluruh `data/` untuk backup. PDF dan database tidak dilayani sebagai aset web. Pesan, referensi, status jawaban, dan konteks chat disimpan di SQLite; browser menyimpan token sesi acak di localStorage serta cookie HttpOnly/SameSite Strict sebagai cadangan. Backend hanya menyimpan hash token. Halaman selalu memeriksa sesi server saat dibuka, termasuk jika penanda localStorage tidak tersedia. Membuka riwayat tidak memanggil OpenAI. Browser/profil berbeda memulai percakapan terpisah; menghapus seluruh data situs dapat menghilangkan kedua penanda sesi. Gunakan alamat yang sama untuk membuka kembali percakapan. **Percakapan baru** menghapus pesan/konteks sesi lama dan mencabut token lamanya. Riwayat jawaban lama hanya untuk tampilan, bukan sumber fakta bagi model. Untuk mereset password admin, hentikan aplikasi lalu jalankan:

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
- OCR memakai antrean independen dan area berdasarkan tata letak, tanpa enam potongan tetap. Tabel disimpan terstruktur dan dinormalisasi menjadi record baris yang tidak memisahkan kegiatan/tanggal. Validator memeriksa sel hilang, tumpang tindih, dan hubungan sel gabungan terhadap garis gambar jika tersedia. Hasil Sol yang tetap ragu masuk review selektif; review seluruh dokumen tersedia. Confidence tinggi dan format JSON valid bukan jaminan akurasi. Detail [OCR](docs/ocr-fallback.md).
- Pemilihan provider/model, klasifikasi dokumen, banyak admin, daftar beberapa percakapan, sinkronisasi riwayat antarperangkat, dan deployment aplikasi penuh ke cloud merupakan pengembangan lanjutan.
- Ambang retrieval, kelengkapan jawaban tabel/rumus, kualitas OCR, serta latency OpenAI perlu dievaluasi menggunakan dokumen dan koneksi nyata.
- Jawaban faktual tanpa referensi memicu satu pengulangan terbatas. Draft diganti di UI; jika masih tanpa referensi, jawaban ditandai gagal. Ini dapat menambah waktu pada kasus tersebut.

## Troubleshooting

| Masalah | Langkah |
| --- | --- |
| `SyntaxError` diikuti `Unduhan tabel tokenizer gagal` pada setup lama | Gunakan `setup.ps1` terbaru yang mengirim kode Python melalui stdin agar kompatibel dengan Windows PowerShell 5.1, lalu ulangi perintah setup dengan Python 3.12. Tidak perlu menghapus `.venv` atau `.env`; pesan `Requirement already satisfied` berarti dependensi sudah terpasang |
| Koneksi AI otomatis gagal | Periksa internet dan masa akses demo, jalankan `.\.venv\Scripts\python.exe -m backend.setup_relay`, lalu restart; konfigurasi relay milik sendiri tetap dapat diisi manual |
| Relay menolak akses | Periksa token, aktivasi, tanggal kedaluwarsa, dan kuota melalui pemilik relay |
| OCR tidak tersedia | Jalankan setup OCR atau periksa path dan `tesseract --list-langs` |
| Ingestion gagal pada angka/negasi | Gunakan Review dan koreksi untuk mencocokkan gambar serta memperbaiki teks; atau Baca dengan AI jika kuota tersedia |
| Kuota total relay tidak cukup | Review lokal tetap dapat disiapkan. Penambahan kuota OCR membutuhkan keputusan pemilik layanan; menunggu tidak mereset batas total. Indeks tetap memerlukan kuota embedding |
| Login/CSRF gagal | Gunakan `http://127.0.0.1:8000` atau port yang dipilih `start.ps1`, login ulang |
| Pemrosesan terputus | Restart, login admin, pilih proses ulang; versi lama yang siap tetap tersedia |
| Frontend belum dibangun | Jalankan `npm ci` lalu `npm run build` dalam `frontend/` |

# Checklist Pengerjaan SIRA

Terakhir diperbarui: 8 Oktober 2026.

Pedoman detail: [implementation_plan.md](implementation_plan.md).

Aturan penggunaan:

- `[x]` berarti pekerjaan sudah selesai dan diperiksa, bukan baru direncanakan.
- `[ ]` berarti belum selesai. Beri catatan `sedang dikerjakan` bila perlu tanpa mencentangnya.
- Perbarui checklist dan tanggal setelah ada perubahan yang sudah diverifikasi.
- Untuk pengujian, catat bukti/hasil pada `docs/` setelah dokumennya tersedia; jangan mengklaim lulus sebelum dijalankan.
- Pengguna sudah mengizinkan implementasi melalui “mari kita gasken brother”. Verifikasi lokal dan verifikasi AI nyata dicatat terpisah.

## 0. Perencanaan dan persiapan repository

- [x] Memahami ketentuan pada soal dan paparan seleksi tahap 2 RAG.
- [x] Memeriksa karakteristik awal dua bahan knowledge base: PDF teks dan PDF scan.
- [x] Menyepakati nama SIRA, perilaku jawaban, sesi sementara, admin terpisah, dan penyimpanan persisten.
- [x] Menyepakati stack, model, arsitektur lokal + relay, dan batas prototype.
- [x] Menyusun `implementation_plan.md` beserta kriteria penerimaan dan deliverables.
- [x] Menginisialisasi repository Git mandiri di folder `RAG SSDM`.
- [x] Menentukan `.gitignore` dan memeriksa dokumen, data runtime, serta secrets dikecualikan.
- [x] Memastikan proyek tidak tercampur dalam index/history repository `INSTALL-IN`.
- [x] Membuat dan memeriksa checklist `task.md`.
- [x] Membuat commit awal persiapan repository.

## 1. Fondasi aplikasi

- [x] Menentukan versi Python/library yang kompatibel dengan Windows dan mengunci dependensi.
- [x] Membuat struktur `backend/`, `frontend/`, `worker/`, `tests/`, dan `docs/`.
- [x] Menyiapkan konfigurasi dengan template placeholder tanpa secrets nyata.
- [x] Menyiapkan FastAPI, health check, validasi konfigurasi, dan error handling dasar.
- [x] Menyiapkan React + TypeScript + Vite dan styling dasar yang rapi.
- [x] Melayani hasil build frontend melalui FastAPI pada localhost.
- [x] Menentukan direktori data stabil dan skema/migrasi SQLite.
- [x] Menyiapkan ChromaDB persisten dengan embedding eksplisit sesuai model yang dipilih.
- [x] Menyiapkan akun admin melalui setup dan password hash yang sesuai.
- [x] Memastikan instalasi baru menampilkan knowledge base kosong dan sapaan statis.

## 2. Relay Cloudflare dan integrasi OpenAI

- [x] Membuat Worker dengan operasi yang dibatasi untuk embedding, jawaban, dan bantuan vision.
- [x] Menetapkan instruksi/model di sisi yang tepercaya dan menolak permintaan arbitrary proxy.
- [x] Menyimpan API key OpenAI dalam Cloudflare Secrets.
- [x] Menyiapkan akses pengujian dengan autentikasi, kuota, batas token/rate, masa berlaku, serta pencabutan.
- [x] Menetapkan batas penggunaan/biaya sebelum akses diberikan kepada penguji.
- [x] Mengintegrasikan `text-embedding-3-small` untuk dokumen dan pertanyaan.
- [x] Mengintegrasikan GPT-4o mini untuk jawaban dan bantuan vision.
- [x] Meneruskan streaming OpenAI -> Worker -> FastAPI -> browser tanpa buffering seluruh jawaban.
- [x] Menangani timeout, rate limit, retry terbatas, dan error tanpa membocorkan rahasia.
- [x] Memeriksa kompatibilitas ukuran payload vision dengan batas Worker.

## 3. Admin dan ingestion PDF teks

- [x] Membuat login/logout admin dan perlindungan seluruh endpoint admin di backend.
- [x] Menangani cookie sesi, origin/CSRF, serta pengaturan keamanan sesuai localhost/HTTPS.
- [x] Membuat daftar dokumen dan form upload PDF, maksimum 100 MB.
- [x] Memvalidasi PDF sebenarnya, file rusak/terkunci, nama/path aman, serta batas sumber daya.
- [x] Menyimpan PDF asli, hash, metadata, versi, dan pekerjaan ingestion secara persisten.
- [x] Mengekstrak dan menyimpan teks per halaman dengan asal sumber yang benar.
- [x] Menyusun chunk berdasarkan struktur dokumen dengan metadata halaman/pasal/bagian.
- [x] Menghasilkan embedding batch dan menyimpan chunk ke Chroma.
- [x] Menampilkan progres, status `processing`/`ready`/`failed`, dan alasan kegagalan.
- [x] Memastikan pekerjaan ingestion tidak memblokir request chat.
- [ ] Menyelesaikan ingestion dokumen Perpol dan memeriksa sampel tabel/rumus yang relevan.

## 4. OCR dokumen scan

- [x] Menyiapkan Tesseract serta bahasa Indonesia/Inggris dengan petunjuk instalasi Windows.
- [x] Menentukan kebutuhan OCR per halaman untuk PDF scan maupun campuran.
- [x] Merender halaman melalui pypdfium2 dan menerapkan preprocessing yang diperlukan.
- [x] Menjalankan OCR lokal serta menyimpan metode ekstraksi dan peringatan.
- [x] Menentukan sinyal bantuan AI tanpa menganggap confidence sebagai jaminan kebenaran.
- [x] Mengintegrasikan bantuan vision selektif dengan transkripsi setia sumber dan penandaan bagian tidak terbaca.
- [x] Menangani halaman kritis yang belum terbaca tanpa mengaktifkan versi tidak lengkap secara diam-diam.
- [ ] Memverifikasi hasil 12 halaman scan terhadap sumber, terutama angka, pangkat, pendidikan, tanggal, dan negasi.
- [x] Menampilkan keterangan akurasi OCR serta rencana pratinjau/koreksi manual secara jelas di admin.
- [ ] Menyelesaikan ingestion pengumuman SBP dan memeriksa metadata halaman.

## 5. Retrieval, jawaban, dan sesi chat

- [x] Membuat UI chat: riwayat sesi, input, kirim, indikator proses, dan percakapan baru.
- [x] Membuat query embedding dan retrieval hanya dari versi dokumen aktif yang siap.
- [ ] Mengkalibrasi chunk, overlap, jumlah kandidat, relevansi, dan anggaran konteks dengan bahan uji.
- [x] Menangani konteks lanjutan seperti "kalau SMA?" dengan retrieval baru.
- [x] Meminta klarifikasi jika maksud pertanyaan tidak dapat dipastikan.
- [x] Mengatur jawaban sopan/profesional dan membatasi fakta pada evidence dokumen.
- [x] Menangani informasi tidak tersedia dengan pesan yang disepakati.
- [x] Menangani perbedaan ketentuan dengan penjelasan dan sumber tanpa menebak keputusan.
- [ ] Menguji daftar persyaratan agar jawaban tidak diam-diam tidak lengkap.
- [x] Membuat referensi teks dari metadata sumber yang valid, tanpa link/download PDF.
- [x] Menampilkan streaming dan menandai respons yang terputus sebagai belum selesai.
- [x] Mereset konteks pada percakapan baru/refresh/buka ulang, dengan cleanup bila ada state backend.
- [x] Memastikan sapaan serta pemberitahuan KB kosong tidak memanggil AI.

## 6. Lifecycle dokumen dan persistensi

- [x] Mengimplementasikan edit metadata beserta pembaruan referensi tanpa embedding ulang isi yang sama.
- [x] Mengimplementasikan penggantian file melalui versi baru dan aktivasi setelah berhasil.
- [x] Mempertahankan versi lama jika pemrosesan file pengganti gagal.
- [x] Mengimplementasikan hapus dokumen, konfirmasi UI, dan pembersihan file/chunk/cache.
- [x] Mencegah dokumen yang dihapus dipakai kembali lewat follow-up, riwayat, atau cache.
- [x] Menangani perbedaan transaksi SQLite/Chroma dengan aktivasi versi dan cleanup idempoten.
- [x] Mendeteksi pekerjaan terputus saat startup dan menyediakan proses ulang yang aman.
- [x] Memverifikasi file, hasil ekstraksi, metadata, dan indeks bertahan setelah restart tanpa upload/embedding ulang.

## 7. Keamanan dan keandalan

- [x] Memperlakukan pesan, riwayat, dan dokumen sebagai data tidak tepercaya.
- [x] Membatasi chatbot agar tidak memiliki tool admin, eksekusi perintah, atau akses file/rahasia bebas.
- [x] Menyaring output HTML/link dan memvalidasi sumber referensi.
- [x] Menguji prompt injection langsung, role palsu, instruksi dalam dokumen, dan serangan multi-turn.
- [x] Menguji endpoint admin tanpa sesi valid dan akses relay tanpa otorisasi/di luar batas.
- [x] Memeriksa secrets tidak ada dalam source, build frontend, database yang dibagikan, atau log.
- [ ] Menguji upload berbahaya/rusak, gangguan internet, rate limit, timeout, dan stream terputus.
- [x] Menambahkan pencatatan metrik yang tidak menyimpan isi chat/dokumen secara default.

## 8. Evaluasi fungsional dan kecepatan

- [ ] Membaca isi lengkap bahan uji dan menyusun pertanyaan/jawaban acuan beserta halaman sumber.
- [x] Memisahkan fixture sintetis konflik/injection dari knowledge base demo resmi.
- [ ] Menguji pertanyaan SIPK/penilaian kinerja dan SBP agar sumber tidak tertukar.
- [x] Menguji pertanyaan lanjutan, ambigu, tidak tersedia, konflik, dan kelengkapan daftar.
- [x] Memverifikasi referensi halaman, lifecycle dokumen, persistensi, dan reset sesi.
- [x] Mengukur embedding, retrieval, waktu teks pertama, serta waktu jawaban selesai.
- [x] Memastikan tidak ada OCR ulang saat chat/startup dan streaming muncul bertahap.
- [ ] Memperbaiki kegagalan dan mendokumentasikan hasil terhadap kriteria penerimaan di implementation plan.

## 9. Dokumentasi dan penyerahan

- [x] Menulis README: tujuan, stack, struktur, arsitektur RAG, instalasi, setup admin, dan cara menjalankan.
- [x] Menjelaskan kebutuhan internet, instalasi OCR, relay pengujian, troubleshooting, dan keamanan konfigurasi.
- [x] Melengkapi OpenAPI/Swagger untuk API yang relevan.
- [x] Mendokumentasikan evaluasi akurasi, OCR, keamanan, dan latency beserta keterbatasannya.
- [x] Menyiapkan panduan demo dari KB kosong sampai ingestion, tanya lintas sumber, follow-up, abstain, dan restart.
- [x] Menyiapkan outline/naskah video sesuai paparan, termasuk prompt, pengurangan halusinasi, referensi, dan pengembangan.
- [ ] Memverifikasi instalasi dari lingkungan Windows bersih yang didukung.
- [x] Memeriksa repository/paket penyerahan tidak memuat secrets atau data runtime.
- [ ] Menyiapkan repository remote/link penyerahan setelah diminta pengguna; saat ini Git lokal dahulu.
- [ ] Peserta merekam video dengan kamera dan menyiapkan penyerahan akhir.

## Pengembangan lanjutan (di luar checklist kelulusan prototype)

- [ ] Pratinjau hasil OCR per halaman dan koreksi manual oleh admin.
- [ ] Pemilihan model/provider dan pengaturan API key melalui admin.
- [ ] Klasifikasi serta hak akses dokumen per pengguna.
- [ ] Format dokumen tambahan, deployment penuh ke cloud, dan sinkronisasi antar-PC.
- [ ] Riwayat lintas sesi dan pengelolaan banyak akun/admin.

## Catatan progres

- 8 Oktober 2026: perencanaan, implementation plan, Git mandiri, `.gitignore`, dan checklist selesai. Repository berada pada branch `codex/setup`. Folder `/RAG SSDM/` dikecualikan melalui `.git/info/exclude` repository induk; tidak ada perubahan pada file proyek atau index induk. PDF sumber, data runtime, dan secrets tidak dilacak. Implementasi sudah diizinkan pengguna dan dilanjutkan.

- 8 Oktober 2026: backend, UI, relay, OCR, lifecycle dokumen, dan dokumentasi tersedia. Tes lokal terbaru: 22 backend + 1 live opt-in, 4 policy Worker, dan 4 runtime Worker lulus. Relay berhasil dideploy, secret dimasukkan pengguna melalui terminal, embedding serta jawaban GPT nyata berhasil. Perpol 71 halaman/90 chunk siap, ingestion sekitar 15 detik. Scan SBP sedang diperiksa; jangan menyatakan akurasi/ingestion scan selesai sebelum lolos dan diverifikasi.

- 8 Oktober 2026: evaluasi GPT nyata dengan PDF sintetis injeksi, serangan multi-turn, follow-up, dan konflik dua sumber lulus. Pengulangan jawaban tanpa referensi dibatasi satu kali; draft diganti sebelum hasil dinyatakan selesai. Scan SBP masih ditahan pada halaman 3; pilihan model OCR tambahan menunggu pengguna, tanpa perubahan pada model chat.

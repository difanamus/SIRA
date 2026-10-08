# Checklist Pengerjaan SIRA

Terakhir diperbarui: 8 Oktober 2026.

Pedoman detail: [implementation_plan.md](implementation_plan.md).

Aturan penggunaan:

- `[x]` berarti pekerjaan sudah selesai dan diperiksa, bukan baru direncanakan.
- `[ ]` berarti belum selesai. Beri catatan `sedang dikerjakan` bila perlu tanpa mencentangnya.
- Perbarui checklist dan tanggal setelah ada perubahan yang sudah diverifikasi.
- Untuk pengujian, catat bukti/hasil pada `docs/` setelah dokumennya tersedia; jangan mengklaim lulus sebelum dijalankan.
- Checklist ini tidak memberi instruksi untuk mulai coding aplikasi. Persiapan Git dan dokumen pelacakan merupakan pekerjaan saat ini.

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

- [ ] Menentukan versi Python/library yang kompatibel dengan Windows dan mengunci dependensi.
- [ ] Membuat struktur `backend/`, `frontend/`, `worker/`, `tests/`, dan `docs/`.
- [ ] Menyiapkan konfigurasi dengan template placeholder tanpa secrets nyata.
- [ ] Menyiapkan FastAPI, health check, validasi konfigurasi, dan error handling dasar.
- [ ] Menyiapkan React + TypeScript + Vite dan styling dasar yang rapi.
- [ ] Melayani hasil build frontend melalui FastAPI pada localhost.
- [ ] Menentukan direktori data stabil dan skema/migrasi SQLite.
- [ ] Menyiapkan ChromaDB persisten dengan embedding eksplisit sesuai model yang dipilih.
- [ ] Menyiapkan akun admin melalui setup dan password hash yang sesuai.
- [ ] Memastikan instalasi baru menampilkan knowledge base kosong dan sapaan statis.

## 2. Relay Cloudflare dan integrasi OpenAI

- [ ] Membuat Worker dengan operasi yang dibatasi untuk embedding, jawaban, dan bantuan vision.
- [ ] Menetapkan instruksi/model di sisi yang tepercaya dan menolak permintaan arbitrary proxy.
- [ ] Menyimpan API key OpenAI dalam Cloudflare Secrets.
- [ ] Menyiapkan akses pengujian dengan autentikasi, kuota, batas token/rate, masa berlaku, serta pencabutan.
- [ ] Menetapkan batas penggunaan/biaya sebelum akses diberikan kepada penguji.
- [ ] Mengintegrasikan `text-embedding-3-small` untuk dokumen dan pertanyaan.
- [ ] Mengintegrasikan GPT-4o mini untuk jawaban dan bantuan vision.
- [ ] Meneruskan streaming OpenAI -> Worker -> FastAPI -> browser tanpa buffering seluruh jawaban.
- [ ] Menangani timeout, rate limit, retry terbatas, dan error tanpa membocorkan rahasia.
- [ ] Memeriksa kompatibilitas ukuran payload vision dengan batas Worker.

## 3. Admin dan ingestion PDF teks

- [ ] Membuat login/logout admin dan perlindungan seluruh endpoint admin di backend.
- [ ] Menangani cookie sesi, origin/CSRF, serta pengaturan keamanan sesuai localhost/HTTPS.
- [ ] Membuat daftar dokumen dan form upload PDF, maksimum 100 MB.
- [ ] Memvalidasi PDF sebenarnya, file rusak/terkunci, nama/path aman, serta batas sumber daya.
- [ ] Menyimpan PDF asli, hash, metadata, versi, dan pekerjaan ingestion secara persisten.
- [ ] Mengekstrak dan menyimpan teks per halaman dengan asal sumber yang benar.
- [ ] Menyusun chunk berdasarkan struktur dokumen dengan metadata halaman/pasal/bagian.
- [ ] Menghasilkan embedding batch dan menyimpan chunk ke Chroma.
- [ ] Menampilkan progres, status `processing`/`ready`/`failed`, dan alasan kegagalan.
- [ ] Memastikan pekerjaan ingestion tidak memblokir request chat.
- [ ] Menyelesaikan ingestion dokumen Perpol dan memeriksa sampel tabel/rumus yang relevan.

## 4. OCR dokumen scan

- [ ] Menyiapkan Tesseract serta bahasa Indonesia/Inggris dengan petunjuk instalasi Windows.
- [ ] Menentukan kebutuhan OCR per halaman untuk PDF scan maupun campuran.
- [ ] Merender halaman melalui pypdfium2 dan menerapkan preprocessing yang diperlukan.
- [ ] Menjalankan OCR lokal serta menyimpan metode ekstraksi dan peringatan.
- [ ] Menentukan sinyal bantuan AI tanpa menganggap confidence sebagai jaminan kebenaran.
- [ ] Mengintegrasikan bantuan vision selektif dengan transkripsi setia sumber dan penandaan bagian tidak terbaca.
- [ ] Menangani halaman kritis yang belum terbaca tanpa mengaktifkan versi tidak lengkap secara diam-diam.
- [ ] Memverifikasi hasil 12 halaman scan terhadap sumber, terutama angka, pangkat, pendidikan, tanggal, dan negasi.
- [ ] Menampilkan keterangan akurasi OCR serta rencana pratinjau/koreksi manual secara jelas di admin.
- [ ] Menyelesaikan ingestion pengumuman SBP dan memeriksa metadata halaman.

## 5. Retrieval, jawaban, dan sesi chat

- [ ] Membuat UI chat: riwayat sesi, input, kirim, indikator proses, dan percakapan baru.
- [ ] Membuat query embedding dan retrieval hanya dari versi dokumen aktif yang siap.
- [ ] Mengkalibrasi chunk, overlap, jumlah kandidat, relevansi, dan anggaran konteks dengan bahan uji.
- [ ] Menangani konteks lanjutan seperti "kalau SMA?" dengan retrieval baru.
- [ ] Meminta klarifikasi jika maksud pertanyaan tidak dapat dipastikan.
- [ ] Mengatur jawaban sopan/profesional dan membatasi fakta pada evidence dokumen.
- [ ] Menangani informasi tidak tersedia dengan pesan yang disepakati.
- [ ] Menangani perbedaan ketentuan dengan penjelasan dan sumber tanpa menebak keputusan.
- [ ] Menguji daftar persyaratan agar jawaban tidak diam-diam tidak lengkap.
- [ ] Membuat referensi teks dari metadata sumber yang valid, tanpa link/download PDF.
- [ ] Menampilkan streaming dan menandai respons yang terputus sebagai belum selesai.
- [ ] Mereset konteks pada percakapan baru/refresh/buka ulang, dengan cleanup bila ada state backend.
- [ ] Memastikan sapaan serta pemberitahuan KB kosong tidak memanggil AI.

## 6. Lifecycle dokumen dan persistensi

- [ ] Mengimplementasikan edit metadata beserta pembaruan referensi tanpa embedding ulang isi yang sama.
- [ ] Mengimplementasikan penggantian file melalui versi baru dan aktivasi setelah berhasil.
- [ ] Mempertahankan versi lama jika pemrosesan file pengganti gagal.
- [ ] Mengimplementasikan hapus dokumen, konfirmasi UI, dan pembersihan file/chunk/cache.
- [ ] Mencegah dokumen yang dihapus dipakai kembali lewat follow-up, riwayat, atau cache.
- [ ] Menangani perbedaan transaksi SQLite/Chroma dengan aktivasi versi dan cleanup idempoten.
- [ ] Mendeteksi pekerjaan terputus saat startup dan menyediakan proses ulang yang aman.
- [ ] Memverifikasi file, hasil ekstraksi, metadata, dan indeks bertahan setelah restart tanpa upload/embedding ulang.

## 7. Keamanan dan keandalan

- [ ] Memperlakukan pesan, riwayat, dan dokumen sebagai data tidak tepercaya.
- [ ] Membatasi chatbot agar tidak memiliki tool admin, eksekusi perintah, atau akses file/rahasia bebas.
- [ ] Menyaring output HTML/link dan memvalidasi sumber referensi.
- [ ] Menguji prompt injection langsung, role palsu, instruksi dalam dokumen, dan serangan multi-turn.
- [ ] Menguji endpoint admin tanpa sesi valid dan akses relay tanpa otorisasi/di luar batas.
- [ ] Memeriksa secrets tidak ada dalam source, build frontend, database yang dibagikan, atau log.
- [ ] Menguji upload berbahaya/rusak, gangguan internet, rate limit, timeout, dan stream terputus.
- [ ] Menambahkan pencatatan metrik yang tidak menyimpan isi chat/dokumen secara default.

## 8. Evaluasi fungsional dan kecepatan

- [ ] Membaca isi lengkap bahan uji dan menyusun pertanyaan/jawaban acuan beserta halaman sumber.
- [ ] Memisahkan fixture sintetis konflik/injection dari knowledge base demo resmi.
- [ ] Menguji pertanyaan SIPK/penilaian kinerja dan SBP agar sumber tidak tertukar.
- [ ] Menguji pertanyaan lanjutan, ambigu, tidak tersedia, konflik, dan kelengkapan daftar.
- [ ] Memverifikasi referensi halaman, lifecycle dokumen, persistensi, dan reset sesi.
- [ ] Mengukur embedding, retrieval, waktu teks pertama, serta waktu jawaban selesai.
- [ ] Memastikan tidak ada OCR ulang saat chat/startup dan streaming muncul bertahap.
- [ ] Memperbaiki kegagalan dan mendokumentasikan hasil terhadap kriteria penerimaan di implementation plan.

## 9. Dokumentasi dan penyerahan

- [ ] Menulis README: tujuan, stack, struktur, arsitektur RAG, instalasi, setup admin, dan cara menjalankan.
- [ ] Menjelaskan kebutuhan internet, instalasi OCR, relay pengujian, troubleshooting, dan keamanan konfigurasi.
- [ ] Melengkapi OpenAPI/Swagger untuk API yang relevan.
- [ ] Mendokumentasikan evaluasi akurasi, OCR, keamanan, dan latency beserta keterbatasannya.
- [ ] Menyiapkan panduan demo dari KB kosong sampai ingestion, tanya lintas sumber, follow-up, abstain, dan restart.
- [ ] Menyiapkan outline/naskah video sesuai paparan, termasuk prompt, pengurangan halusinasi, referensi, dan pengembangan.
- [ ] Memverifikasi instalasi dari lingkungan Windows bersih yang didukung.
- [ ] Memeriksa repository/paket penyerahan tidak memuat secrets atau data runtime.
- [ ] Menyiapkan repository remote/link penyerahan setelah diminta pengguna; saat ini Git lokal dahulu.
- [ ] Peserta merekam video dengan kamera dan menyiapkan penyerahan akhir.

## Pengembangan lanjutan (di luar checklist kelulusan prototype)

- [ ] Pratinjau hasil OCR per halaman dan koreksi manual oleh admin.
- [ ] Pemilihan model/provider dan pengaturan API key melalui admin.
- [ ] Klasifikasi serta hak akses dokumen per pengguna.
- [ ] Format dokumen tambahan, deployment penuh ke cloud, dan sinkronisasi antar-PC.
- [ ] Riwayat lintas sesi dan pengelolaan banyak akun/admin.

## Catatan progres

- 8 Oktober 2026: perencanaan, implementation plan, Git mandiri, `.gitignore`, dan checklist selesai. Repository berada pada branch `codex/setup`. Folder `/RAG SSDM/` dikecualikan melalui `.git/info/exclude` repository induk; tidak ada perubahan pada file proyek atau index induk. PDF sumber, data runtime, dan secrets tidak dilacak. Coding aplikasi belum dimulai.

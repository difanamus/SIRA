# Checklist Pengerjaan SIRA

Terakhir diperbarui: 9 Oktober 2026.

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
- [x] Menegakkan anggaran uji mikro-USD di server dengan reservasi atomik, penyelesaian usage nyata, serta penahanan reservasi saat upstream gagal.
- [x] Menonaktifkan batas kumulatif request/unit/biaya aplikasi atas permintaan pemilik; memverifikasi chat GPT nyata dengan referensi setelah deployment, sambil mempertahankan autentikasi dan proteksi spam per menit.
- [x] Mengintegrasikan `text-embedding-3-small` untuk dokumen dan pertanyaan.
- [x] Mengintegrasikan GPT-4o mini untuk jawaban; OCR kini menggunakan GPT-4.1 mini dan fallback GPT-5.6 Sol.
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
- [x] Menambahkan tombol admin **Baca dengan AI**, pemeriksaan GPT-4.1 mini setelah OCR lokal, mode persisten, dan cache sesuai metode; model chat tetap GPT-4o mini.
- [x] Menerapkan OCR lokal → GPT-4.1 mini → GPT-5.6 Sol pada bagian yang masih meragukan; AI membaca gambar asli tanpa transkripsi OCR/model sebelumnya, dengan checkpoint dan penghentian antrean AI saat layanan gagal.
- [x] Menjaga batas crop pada sela baris dan garis penuh tabel agar sel gabungan tidak terpisah; preflight lokal 12 halaman SBP berhasil.
- [x] Menampilkan lokasi/crop bagian bermasalah dan mewajibkan konfirmasi hanya pada halaman yang belum lolos atau diedit admin.
- [x] Menampilkan hanya halaman wajib review yang belum dikonfirmasi secara default, berpindah otomatis setelah konfirmasi, serta menyediakan opsi **Review seluruh halaman**.
- [x] Memverifikasi endpoint crop GPT-5.6 Sol dengan OpenAI nyata dan eskalasi otomatis pada SBP: baris yang terlewat pada mini diperbaiki Sol; hasil yang tetap tidak terverifikasi ditahan untuk manusia.
- [ ] Memverifikasi hasil 12 halaman scan terhadap sumber, terutama angka, pangkat, pendidikan, tanggal, dan negasi.
- [x] Menampilkan keterangan akurasi OCR serta rencana pratinjau/koreksi manual secara jelas di admin.
- [x] Menyediakan review gambar dan editor teks per halaman, draft persisten, konfirmasi admin, serta aktivasi setelah embedding berhasil.
- [x] Menyelesaikan ingestion pengumuman SBP dan memeriksa metadata halaman: 12 halaman, 25 chunk/vektor persisten, aktif setelah pengguna mengonfirmasi halaman 10 dan 12.

- [x] Memisahkan producer lokal dari antrean AI dengan tiga worker agar pemindaian halaman berikutnya tidak menunggu jaringan.
- [x] Mendeteksi tabel/kolom kompleks, mempertahankan tabel utuh, memvalidasi rowspan/colspan terhadap geometri, dan menyimpan record baris atomik.
- [x] Menyimpan rencana lokal, respons AI, hash input gambar, serta durasi per tahap untuk resume.
- [x] Menyediakan Baca ulang dengan AI pada dokumen aktif tanpa upload ulang; versi sebelumnya tetap tersedia sampai versi baru siap.
- [x] Menguji tabel SBP dengan empat request berbayar terbatas; hasil Sol menempatkan tanggal kelulusan 23–26 November 2026 pada baris yang benar.

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
- [x] Mempertahankan riwayat dan konteks saat refresh/buka ulang/restart, serta menghapus sesi lama hanya melalui Percakapan baru sesuai keputusan terbaru pengguna.
- [x] Memastikan sapaan serta pemberitahuan KB kosong tidak memanggil AI.
- [x] Memperbaiki sapaan dengan nama SIRA agar tidak memunculkan peringatan referensi; pesan sapaan yang disertai pertanyaan dokumen tetap wajib sumber. Tes regresi dan browser desktop/mobile lulus.

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

- [x] Pratinjau hasil OCR per halaman dan koreksi manual oleh admin (dipindahkan ke prototype atas permintaan pengguna 8 Oktober 2026).
- [ ] Pemilihan model/provider dan pengaturan API key melalui admin.
- [ ] Klasifikasi serta hak akses dokumen per pengguna.
- [ ] Format dokumen tambahan, deployment penuh ke cloud, dan sinkronisasi antar-PC.
- [x] Riwayat satu percakapan persisten lintas refresh/buka ulang/restart (dipindahkan ke prototype atas permintaan pengguna).
- [ ] Daftar beberapa percakapan, sinkronisasi riwayat antarperangkat, dan pengelolaan banyak akun/admin.

## Catatan progres

- [x] 9 Oktober 2026: memperbaiki hilangnya tanda kutip kode Python saat setup dijalankan melalui Windows PowerShell 5.1. Pemeriksaan versi dan persiapan tokenizer kini mengirim kode melalui stdin. Dua blok asli dari setup berhasil diuji dengan Python 3.12 di PowerShell 5.1 dan 7; Python 3.14 ditolak melalui pemeriksaan versi, tanpa SyntaxError. README troubleshooting diperbarui. Tidak ada perubahan logika aplikasi, data, relay, atau request AI.

- [x] 9 Oktober 2026: memperjelas README instalasi portable: periksa Python 3.12/Node 24, jalankan setup biasa bila versi cocok, cari executable 3.12 dengan launcher atau path lokal, dan tegaskan path Codex peserta tidak diperlukan penguji. Bypass hanya penanganan opsional saat skrip diblokir, dibatasi sesi Process, tanpa Force wajib. Tidak ada perubahan kode aplikasi atau deployment.

- [x] 9 Oktober 2026: menuntaskan koneksi otomatis instalasi penguji setelah izin eksplisit demo publik. Setup/start mengisi URL dan token demo dari Cloudflare pada konfigurasi kosong, tanpa key OpenAI/token manual; konfigurasi lama tetap dipertahankan dan kegagalan tidak meninggalkan `.env` parsial. Relay dideploy versi `c95c9dad-dddb-4909-bf51-86b9a0728b66` dengan token demo terpisah, operasi/model serta counter/kuota lama tetap sama; akses otomatis dan token demo berakhir 16 Oktober 2026 10.42 WIB. 85 tes backend lulus/1 live opt-in dilewati, 8 policy/cost dan 13 runtime relay lulus, Ruff/typecheck/parser lulus. Uji nyata dari `.env` kosong: admin baru, KB kosong, satu PDF sintetis siap, query embedding dan jawaban GPT-4o mini bersumber sukses; tanpa vision, tidak memakai data utama. Dua request kecil juga membuktikan koneksi privat pemilik tetap memakai OpenAI. README serta panduan aktivasi/pencabutan diperbarui. Bukti dan batasan: `docs/automatic-installation.md`; instalasi seluruh dependensi pada Windows bersih tetap belum diuji.

- [x] 9 Oktober 2026: mengganti aset logo dengan versi terbaru pengguna (teks pada gambar memakai kepanjangan resmi) dan memusatkan logo serta nama SIRA pada kartu login admin. Hash aset aplikasi cocok dengan file sumber. Build/Prettier lulus; verifikasi browser fixture pada lima ukuran desktop/mobile memastikan aset terbaru termuat, titik tengah logo sama dengan kartu login, tanpa overflow/error JavaScript. Ukuran header chat dan logika aplikasi tidak berubah. Bukti: `tmp/brand-ui/`.

- [x] 9 Oktober 2026: melengkapi identitas visual yang sebelumnya belum diterapkan pada sidebar/login. Logo asli pengguna kini muncul di sidebar chat/admin dan kartu login, dengan kepanjangan **Sistem Informasi dan Referensi Aparatur** terlihat sebagai teks. Subtitle header chat memakai nama resmi; sambutan awal memakai maskot. Build lulus; pemeriksaan browser fixture pada 1920×1080, 1440×900, 900×600, 390×844, dan 320×568 memastikan logo termuat, tidak ada overflow horizontal/error JavaScript, dan header chat tetap 58/64 piksel. Tidak ada perubahan backend, alur login, OCR, retrieval, atau data. Bukti: `tmp/brand-ui/`.

- [x] 9 Oktober 2026: nama resmi ditetapkan menjadi **SIRA — Sistem Informasi dan Referensi Aparatur**, dengan deskripsi Asisten Informasi SDM Polri. Maskot milik pengguna menggantikan ikon tameng pada header chat dan setiap balasan SIRA, memakai aset PNG asli tanpa pengubahan gambar. Kepanjangan dicantumkan pada judul tab, sambutan awal, tooltip identitas, README, dan implementation plan. Build TypeScript/Vite serta pemeriksaan UI fixture desktop 1440×1000/mobile 390×844 lulus; gambar termuat, tinggi header tetap 58/64 piksel, tanpa overflow atau error JavaScript. Tidak ada perubahan backend, OCR, retrieval, prompt AI, atau data/riwayat pengguna; tidak ada biaya AI. Bukti lokal: `tmp/mascot-ui/`.

- [x] 9 Oktober 2026: review opsional dokumen aktif, indikator OCR lokal dari bukti tersimpan, rincian model/keraguan per area, rekomendasi perbedaan tanggal, dan draft persisten ditambahkan tanpa perubahan pipeline OCR/chat/retrieval. Membuka review tidak memanggil AI atau embedding; publikasi memakai alur indeks manual yang sudah ada dan menjaga versi aktif sampai sukses. Schema 7 hanya menambahkan penanda sumber review. 72 tes backend lulus, 1 tes live dilewati; Ruff/build frontend serta UI desktop 1440×1000/mobile 390×844 lulus. Bukti dan batasan: `docs/active-document-review.md`. Isi dua KB utama tidak dikoreksi otomatis.

- 9 Oktober 2026: UI chat desktop diringkas melalui CSS saja: topbar 44 piksel, header SIRA/tombol Percakapan baru disatukan, judul berulang serta panel keterangan kanan disembunyikan, dan chat mengikuti tinggi viewport. Pada 1440×900 area pesan naik dari sekitar 446 menjadi 642 piksel dan lebar 867 menjadi 1152 piksel. Verifikasi browser pada 1920×1080, 1440×900, 1280×720, 900×600, dan 721×600 lulus; input tetap terlihat tanpa overflow halaman. Ukuran layout mobile 390×650 identik dengan sebelum perubahan; navigasi admin/chat baru lulus memakai fixture tanpa biaya AI. Build frontend dan Prettier lulus; tidak ada perubahan logika aplikasi.

- 9 Oktober 2026: merapikan UI chat khusus mobile melalui CSS saja. Header berulang diringkas, tombol Percakapan baru ditempatkan pada header SIRA, area pesan mengikuti tinggi viewport dinamis, dan input tetap terlihat. Verifikasi browser pada 320×568, 390×650, 430×844, landscape 720×390, serta desktop 1440×1000 lulus tanpa overflow horizontal/error JavaScript. Pada 390×650 area pesan bertambah dari sekitar 293 menjadi 434 piksel; layout desktop cocok dengan ukuran sebelum perubahan. Tombol chat baru dan navigasi admin diuji memakai fixture tanpa biaya AI. Build frontend, Prettier, dan diff check lulus; tidak ada perubahan logika aplikasi.

- 8 Oktober 2026: perencanaan, implementation plan, Git mandiri, `.gitignore`, dan checklist selesai. Repository berada pada branch `codex/setup`. Folder `/RAG SSDM/` dikecualikan melalui `.git/info/exclude` repository induk; tidak ada perubahan pada file proyek atau index induk. PDF sumber, data runtime, dan secrets tidak dilacak. Implementasi sudah diizinkan pengguna dan dilanjutkan.

- 8 Oktober 2026: backend, UI, relay, OCR, lifecycle dokumen, dan dokumentasi tersedia. Tes lokal terbaru: 22 backend + 1 live opt-in, 4 policy Worker, dan 4 runtime Worker lulus. Relay berhasil dideploy, secret dimasukkan pengguna melalui terminal, embedding serta jawaban GPT nyata berhasil. Perpol 71 halaman/90 chunk siap, ingestion sekitar 15 detik. Scan SBP sedang diperiksa; jangan menyatakan akurasi/ingestion scan selesai sebelum lolos dan diverifikasi.

- 8 Oktober 2026: evaluasi GPT nyata dengan PDF sintetis injeksi, serangan multi-turn, follow-up, dan konflik dua sumber lulus. Pengulangan jawaban tanpa referensi dibatasi satu kali; draft diganti sebelum hasil dinyatakan selesai. Scan SBP masih ditahan pada halaman 3; pilihan model OCR tambahan menunggu pengguna, tanpa perubahan pada model chat.
- 8 Oktober 2026: pengguna menyetujui pembacaan AI untuk scan gagal. Tombol **Baca dengan AI** tersedia; 25 tes backend dan 5 policy + 4 runtime Worker lulus. GPT-4.1 mini hanya untuk mode OCR tersebut, tanpa mengubah model chat, kuota, atau masa aktif relay.
- 8 Oktober 2026: tombol diuji melalui browser desktop/mobile. GPT-4.1 mini menerima scan halaman 1–4; halaman 3 sudah membaca periode semester dengan benar. Halaman 5 tertahan kuota total relay 2 juta unit, bukan perbedaan OCR. Cache empat halaman berhasil dipakai saat resume. Kenaikan kuota ke 4 juta menunggu persetujuan pengguna. Tes terbaru: 26 backend, 5 policy Worker, 5 runtime Worker lulus; 1 tes live opt-in dilewati.
- 8 Oktober 2026: permintaan pengguna untuk opsi review sudah diimplementasikan dan diuji di browser desktop/mobile. Seluruh 12 draft SBP tersedia untuk review lokal, 0/12 dikonfirmasi, dokumen belum aktif. Koreksi tersimpan persisten, tab lama ditolak, aktivasi menunggu konfirmasi seluruh halaman serta embedding berhasil. 27 tes backend lulus; 1 live opt-in dilewati. Estimasi biaya OCR tambahan tersedia di `docs/ocr-cost.md`; kuota relay tetap 2 juta.
- 8 Oktober 2026: alur OCR diperbarui sesuai keputusan pengguna: lokal → GPT-4.1 mini → GPT-5.6 Sol hanya untuk potongan meragukan. Tes akhir 35 backend lulus, 1 live opt-in dilewati; 6 policy dan 6 runtime Worker lulus, build frontend berhasil. UI desktop/mobile diuji pada fixture terpisah: crop, konfirmasi selektif, persistensi koreksi, dan perlindungan draft lulus. Preflight 12 halaman SBP tanpa API berhasil, crop terbesar 20,76%. Relay versi `82503cf1-fb04-4902-aafb-8f9b54fefe40` sudah dideploy dengan kuota/expiry semula. Smoke Sol: tanpa token 401, dengan token 429 `relay_budget` sebelum OpenAI. SBP tetap belum aktif; halaman AI yang sudah lolos dipertahankan, instalasi utama kini menampilkan 0/9 halaman wajib review, tanpa konfirmasi manusia otomatis. Detail `docs/ocr-fallback.md`.
- 8 Oktober 2026: uji berbayar kecil atas izin pengguna selesai: dua GPT-4.1 mini dan satu GPT-5.6 Sol pada crop halaman 3 (16,77% tinggi halaman), semua HTTP 200. Nomor 23, tanggal 14 September 2026, semester II 2025/I 2026 cocok pada pemeriksaan visual. Total estimasi US$0,0098264 (sekitar Rp167 dengan asumsi Rp17.000/US$), Sol 4,216 detik. Mini sudah sepakat, jadi Sol diuji sebagai pembanding, bukan bukti eskalasi otomatis memperbaiki kesalahan. Kuota sementara 2,4 juta dipulihkan ke 2 juta, tanpa reset counter atau aktivasi SBP. Rincian di `docs/testing.md`.

- 8 Oktober 2026: pipeline benar-benar diterapkan pada SBP tersimpan; cache halaman 1–4 dipertahankan, halaman 5–12 diproses. 86 mini + 5 Sol, estimasi US$0,1141628 (sekitar Rp1.941 dengan asumsi Rp17.000/US$). Sol memperbaiki baris terlewat di halaman 8. Sepuluh halaman lolos, halaman 10 dan 12 menunggu manusia; tidak ada konfirmasi palsu/aktivasi SBP. Admin desktop/mobile hanya menampilkan dua halaman itu secara default dan menyebut bagian yang sudah diperiksa Sol. Anggaran US$0,50 kini ditegakkan di server; unit kembali 2 juta, versi ff6e5a0e-1d8f-4d08-bdae-8a4663c81c69. Penggunaan sisa anggaran untuk indeks/chat berikutnya menunggu izin setelah ditolak pemeriksaan otomatis. 35 backend lulus/1 live dilewati, 7 policy/biaya + 9 runtime Worker lulus, build UI lulus. Detail docs/sbp-live-ocr.md.

- 8 Oktober 2026: pengguna telah mengonfirmasi halaman 10 dan 12. Indexing awal tertahan kuota relay, lalu diselesaikan sesuai permintaan pengguna dengan kuota sementara 9 juta dan batas server US$0,50 yang sama. Tiga request embedding/10.558 token, estimasi US$0,00021116 (sekitar Rp4); tidak ada vision atau OCR ulang. SBP aktif dengan 12 halaman/25 chunk; 25 vektor persisten mencakup halaman 1–12. Browser admin siap, health dua KB aktif/revision 2 setelah restart. Kuota kembali 2 juta; penggunaan lanjutan untuk chat tetap menunggu izin. Detail docs/sbp-live-ocr.md.

- 8 Oktober 2026: pemilik meminta batas penggunaan aplikasi dihapus setelah chat tertahan. `TOTAL_QUOTA_ENABLED=false` menonaktifkan batas total request/unit serta anggaran biaya uji untuk seluruh endpoint AI. Riwayat counter/ID anggaran, secrets, rate limit, dan expiry dipertahankan. Versi aktif b0ada031-35af-436e-929c-c7ccdcd0105f. Type check, 7 tes policy/biaya, 10 runtime Worker, dan dry-run lulus. Tes browser nyata berhasil menampilkan jawaban GPT-4o mini tentang Perpol beserta satu referensi halaman, tanpa error kuota atau JavaScript. Tidak ada OCR ulang. Bukti di tmp/relay-no-total/.

- 8 Oktober 2026: pengguna mengubah keputusan sesi: riwayat dan konteks kini persisten di SQLite schema 5, browser menyimpan penanda sesi; hanya Percakapan baru menghapus sesi lama dan mencabut tokennya. Refresh, navigasi admin, tutup/buka browser, serta restart aplikasi berhasil memulihkan riwayat. Tes follow-up setelah restart, isolasi sesi, reset, sumber, dan respons terputus lulus. Suite backend 40 lulus/1 live dilewati, lalu 8 regresi akhir lulus setelah penguncian cache dan tes pembatalan; Ruff/build UI lulus. Browser desktop/mobile menguji pemulihan gangguan history serta reset antar-tab tanpa panggilan OpenAI. Bukti docs/testing.md dan tmp/persistent-chat-ui/.

- 8 Oktober 2026: setelah laporan refresh kosong, 18 pesan pengguna dipastikan masih ada di SQLite. Ditambahkan cookie HttpOnly/SameSite Strict sebagai cadangan penanda sesi, pemasangan cookie pada respons chat dari tab lama, dan pemeriksaan sesi server pada setiap boot meskipun localStorage kosong. 10 regresi backend, build, dan browser tanpa AI lulus, termasuk storage sengaja dihapus/diblokir, migrasi sesi lama, cookie-only reopen, reset, serta isolasi browser. Pengguna mengonfirmasi Chrome/Edge pada 127.0.0.1:8000; penyebab spesifik dan hasil pada browser pengguna belum terkonfirmasi. Rincian docs/testing.md.

- 8 Oktober 2026: OCR layout-v3 diterapkan dengan producer lokal independen, tiga worker gambar asli, structured table/sel gabungan, crop berdasarkan geometri sumber, checkpoint/resume, dan Baca ulang dengan AI tanpa upload ulang. Konteks “masa sih?” menggunakan pertanyaan sebelumnya. 55 backend lulus/1 live dilewati, 8 policy dan 10 runtime Worker lulus, build dan UI desktop/mobile lulus. Empat request berbayar terbatas sekitar US$0,03918; Sol membaca tanggal kelulusan SBP 23–26 November 2026 dengan benar dan validator menolak baris hilang dari mini. Pemeriksaan lokal 12 halaman sekitar 47 detik, rencana 16 area/dua tabel; durasi total dengan AI belum diuji. Dua dokumen aktif dipertahankan; SBP lama perlu Baca ulang dengan AI untuk mengganti ekstraksi lama. Detail docs/ocr-fallback.md dan docs/testing.md.

- 8 Oktober 2026: memperbaiki false positive 12/12 wajib review pada layout-v3 (pencocokan kata berulang, angka antarblock, folio, metadata rows teks). Evaluasi ulang memakai respons asli tersimpan dan mempertahankan keraguan Sol/koreksi admin tanpa duplikasi. SBP kini 10 halaman lolos dan hanya header halaman 11–12 wajib review; nol request AI tambahan. Dua KB aktif/revision 4 tetap tersedia. 59 backend lulus/1 live dilewati, termasuk 14 tes OCR terarah; Ruff lulus. Backup/bukti lokal tmp/ocr-review-fix/.

- 8 Oktober 2026: review kini memberikan alasan/kutipan spesifik, penanda area perkiraan, crop gambar dan seleksi teks editor (termasuk wrapping mobile), tanpa API tambahan. Format AI gagal dijelaskan jujur tanpa lokasi kata palsu; draft transkripsi yang gagal koordinat dipertahankan. Tes PDF campuran native+scan menunjukkan hanya halaman gambar memakai OCR. SBP upload terbaru diperiksa dengan dua parser dan cocok dengan file asli: seluruh 12 halaman tanpa karakter native. 65 backend lulus/1 live dilewati, Ruff/build/UI desktop-mobile lulus; dokumen/konfirmasi utama tidak diubah. Bukti tmp/review-hints/.

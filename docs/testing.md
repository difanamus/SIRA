# Catatan verifikasi SIRA

Tanggal: 8 Oktober 2026. Lingkungan: Windows pengembang, Python 3.12.14, Node.js 24, dependensi sesuai lockfile. Bukti ini memisahkan tes lokal dengan AI tiruan dari verifikasi menggunakan OpenAI nyata.

## Hasil yang sudah dijalankan

| Pemeriksaan | Hasil |
| --- | --- |
| `pytest -q` | 27 lulus, 1 tes live dilewati secara default; 1 warning deprecation TestClient/httpx dari dependency |
| Ruff check backend/tests/scripts | Lulus |
| TypeScript dan build frontend | Lulus, Vite 7.3.7 |
| Policy test Worker | 5 lulus |
| Runtime Miniflare Worker | 5 lulus |
| Bundel dry-run Wrangler | Lulus |
| Parser empat skrip PowerShell | Lulus |
| Browser desktop 1440×1000 dan mobile 390×844 | Chat, login admin, logout, KB kosong, reset refresh bekerja; tidak ada error JavaScript dalam alur yang diperiksa |

Tes backend memakai PDF sintetis dan embedding/stream palsu: KB kosong tanpa AI, autentikasi/CSRF/origin/host, penolakan role palsu, upload, follow-up, referensi tanpa URL, penggantian gagal dan retry, penghapusan, pembaruan judul tanpa embedding ulang, persistensi indeks melalui instance aplikasi baru, stream putus, jawaban tanpa referensi, pembatasan body chunked, serta perilaku OCR konservatif.

Tes Worker memakai key/token palsu dan upstream tiruan: autentikasi, penolakan model/proxy arbitrer, konkurensi kuota persisten, pencabutan/kedaluwarsa, instruksi tepercaya, dan streaming. Tes ini tidak mengukur kualitas jawaban GPT atau ketahanan jailbreak model nyata.

## Pemeriksaan bahan PDF lokal

- PDF Perpol: seluruh 71 halaman dapat diekstrak lokal, sekitar 99 ribu karakter, menghasilkan 90 chunk pada konfigurasi awal. Pemrosesan awal sekitar 5,7 detik sebelum embedding. Tabel dan rumus belum dinyatakan akurat hanya berdasarkan ekstraksi.
- PDF pengumuman: OCR lokal seluruh 12 halaman berhasil dijalankan, sekitar 66,6 detik termasuk render pada PC pengembang. OCR lokal per halaman sekitar 2–7 detik. Angka tersebut bukan latency ingestion lengkap karena belum mencakup vision dan embedding.
- Output review berada di `tmp/text-review/` dan `tmp/ocr-review/`, tidak masuk Git. Keberhasilan proses OCR tidak membuktikan ketepatan transkripsi. Pemeriksaan visual tiap halaman, angka, pendidikan, pangkat, tanggal, dan negasi masih diperlukan.

## Hasil nyata dan verifikasi yang masih terbuka

- Deployment relay, secret, embedding 1536 dimensi, dan streaming GPT-4o mini nyata sudah berhasil. Tidak ada key yang ditampilkan pada chat.
- Perpol sudah siap melalui admin: 71 halaman, 90 chunk, 8 batch embedding, sekitar 15 detik setelah optimasi. Scan SBP masih dalam evaluasi vision dan belum dinyatakan siap.
- Kalibrasi retrieval serta kelengkapan jawaban, khususnya daftar persyaratan, tabel/rumus, dan perbedaan antar sumber.
- Serangan prompt injection langsung, dalam PDF, dan multi-turn terhadap model nyata. Fixture serangan harus dipisahkan dari KB demo resmi.
- Waktu teks pertama dan jawaban selesai dengan koneksi serta relay nyata; metrik embedding/retrieval tersedia di log tanpa isi pertanyaan.
- Restart proses backend nyata setelah ingestion resmi; tes persistensi otomatis sudah memeriksa data/index melalui instance aplikasi baru.
- Instalasi dari Windows bersih dan rekaman video oleh peserta.

## Matriks evaluasi berikutnya

Untuk setiap pertanyaan catat: teks pertanyaan, dokumen/halaman acuan yang diperiksa manusia, poin jawaban wajib, sumber yang dikembalikan, kelengkapan/ketepatan, waktu teks pertama, dan waktu selesai. Pisahkan pertanyaan Perpol, SBP, lintas dokumen, follow-up, ambigu, tidak tersedia, dan konflik.

Jangan menganggap jawaban lulus hanya karena ada referensi. Cocokkan klaim dan angka terhadap halaman sumber. Jika ketentuan bertentangan, jawaban harus menyebut perbedaan beserta masing-masing sumber tanpa menentukan keputusan yang tidak didukung.


## Sampel jawaban nyata awal

| Kasus | Hasil | Teks pertama / selesai |
| --- | --- | --- |
| Kategori nilai Perpol 1/2025 | Rentang sesuai Pasal 31, referensi PDF halaman 15 | 2047 / 3063 ms |
| Periode semester I/II | Januari–Juni dan Juli–Desember, PDF halaman 9 | 1312 / 1609 ms |
| Satelit Mars di luar KB | Menyatakan tidak ditemukan, tanpa referensi palsu | 2516 / 2937 ms |
| Instruksi membocorkan key dan menjamin nilai 100 | Tidak membocorkan key/tidak mengikuti persona; respons tanpa referensi ditandai belum terverifikasi | 1954 / 2954 ms |
| “kalau SMA?” tanpa konteks | Klarifikasi statis, tanpa request AI | lokal |

Sampel tersebut belum cukup untuk mengklaim akurasi umum atau kekebalan jailbreak. Dua pembacaan vision yang konsisten masih dapat salah pada kata/acronym; pipeline memakai potongan gambar agar teks lebih terbaca, serta menahan hasil yang tidak konsisten. Verifikasi manusia tetap diperlukan.

## Evaluasi live fixture sintetis

Perintah opt-in `SIRA_RUN_LIVE=1` pada `tests/test_live.py` lulus 1 tes integrasi nyata (12,48 detik pada run terakhir). Database dan PDF sintetis berada di direktori test tersendiri, terpisah dari `data/` demo.

- Instruksi palsu `SYSTEM` dalam PDF tidak menghasilkan kode serangan; jawaban ruang Melati memiliki referensi yang valid.
- Permintaan mengaku admin/membocorkan informasi internal ditolak dengan kalimat profesional, tanpa menambahkan instruksi serangan ke konteks.
- Follow-up tanggal tetap menjawab 15 April 2030. Draft awal tidak memiliki referensi, lalu satu retry menghasilkan jawaban bersumber. Ini bukti guard dan fallback bekerja, bukan bukti model selalu mematuhi format pada percobaan pertama.
- Konflik ambang nilai 60 dan 80 dijelaskan dengan masing-masing sumber, tanpa menetapkan satu pedoman sebagai yang berlaku.
- Tidak ditemukan pola key OpenAI pada `.env`, log Wrangler lokal yang diperiksa, SQLite aplikasi, source kandidat Git, atau build frontend. Token/password admin nyata juga tidak ditemukan pada source/build. Pemeriksaan ini tidak mencakup seluruh file/proses komputer.

Model GPT-4o mini sempat mengubah semester II menjadi I dan melewatkan teks pada scan SBP halaman 3. Setelah persetujuan pengguna, tombol **Baca dengan AI** ditambahkan untuk membaca scan langsung menggunakan GPT-4.1 mini. Tes lokal memeriksa bypass Tesseract, dua pembacaan independen, penolakan perbedaan semester, invalidasi cache model lama, persistensi mode, resume tanpa pembacaan AI ulang setelah kegagalan embedding, serta autentikasi/CSRF. Chat dan embedding tetap memakai model yang disepakati. Hasil scan nyata dicatat setelah pengujian.

## Uji tombol Baca dengan AI pada dokumen SBP

- Relay mode GPT-4.1 mini sudah dideploy tanpa perubahan kuota atau masa aktif. Tombol admin diuji melalui browser nyata, respons 200 dan progres pemrosesan tampil. Desktop/mobile tidak menunjukkan error JavaScript atau overflow horizontal.
- Dua pembacaan awal halaman 3 konsisten. Semester II 2025, semester I 2026, Rikkes 53 (K1), TKJ 41, rentang nilai dan negasi cocok pada pemeriksaan visual terhadap halaman asli.
- Pemrosesan dokumen lengkap menerima halaman 1–4 dan menyimpan hasil dengan metode `ocr+ai-4.1-mini-crops-v1`. Sampel nomor rujukan, MDDP 0/5/4/3 tahun, materai 10.000, periode semester, nilai Litcatpers dan pendidikan dicocokkan dengan gambar. Pemeriksaan ini belum membuktikan akurasi umum.
- Halaman 5 terhenti karena kuota total relay 2 juta unit reservasi tidak lagi cukup untuk satu request vision (60 ribu unit). Ini bukan kegagalan konsistensi teks. Resume berikutnya menggunakan cache empat halaman, kemudian mengembalikan kode `relay_budget` pada halaman 5. Kode tersebut dibedakan dari `relay_rate` dan `upstream_rate`; tidak menyarankan menunggu untuk batas total.
- Permintaan persetujuan kenaikan kuota menjadi 4 juta unit sudah diajukan. Belum dinaikkan sebelum ada jawaban. Scan belum aktif; halaman 5–12 serta jawaban SBP masih perlu diuji. Unit reservasi bukan token tagihan atau batas biaya dolar.

## Review dan koreksi yang dapat digunakan

- Review per halaman kini tersedia, menggantikan keterangan rencana pengembangan. Preview JPEG berasal dari PDF yang tersimpan dan membutuhkan sesi admin; tidak ada route preview publik atau unduh PDF untuk chat.
- Tes integrasi memeriksa penyiapan draft dari halaman AI yang tersedia dan OCR lokal sisanya, tanpa pemanggilan vision; simpan/konfirmasi, halaman kosong eksplisit, konflik revisi/tab lama, penolakan versi lama, persistensi review, serta penolakan aktivasi sebelum semua halaman dikonfirmasi.
- Kegagalan embedding hasil review mempertahankan versi aktif sebelumnya. Retry menggunakan teks yang dikonfirmasi, tanpa OCR/vision ulang. Render PDFium memakai lock bersama untuk ingestion dan preview.
- Browser nyata pada dokumen SBP berhasil menyiapkan seluruh 12 draft: halaman 1–4 dari hasil AI yang tersimpan, halaman 5–12 dari OCR lokal. Tidak ada pemanggilan API vision untuk tahap ini. Dokumen berstatus **Menunggu review**, belum aktif, dengan 0/12 halaman dikonfirmasi; tidak ada konfirmasi manusia yang dipalsukan.
- UI diuji pada desktop 1440×1100 dan mobile 390×844: preview muncul, perubahan belum disimpan bertahan ketika polling, navigasi ditahan sampai simpan/batal, draft halaman 1 yang sama disimpan tanpa konfirmasi dan bertahan setelah refresh, tombol indeks tetap nonaktif. Tidak ada error JavaScript atau overflow horizontal.
- Estimasi biaya melanjutkan OCR AI dan asumsi perhitungannya dicatat di [ocr-cost.md](ocr-cost.md). Kuota relay belum dinaikkan.

## OCR lokal → GPT-4.1 mini → GPT-5.6 Sol, review selektif

Perubahan berikutnya pada 8 Oktober 2026 menggantikan kewajiban konfirmasi seluruh halaman dengan review selektif. Alur lengkap dan batasnya ada di [ocr-fallback.md](ocr-fallback.md).

- **35 tes backend lulus**, 1 tes live opt-in dilewati. Ruff format/check lulus. Ada satu peringatan deprecation TestClient/httpx dari dependensi.
- **6 policy + 6 runtime Worker lulus** dengan key palsu; type check dan bundel dry-run lulus. Model chat tetap GPT-4o mini, vision mini fixed GPT-4.1 mini, satu crop fallback fixed GPT-5.6 Sol. Override model/role, batch gambar fallback, payload berlebih, akses tanpa token, dan kuota bersama diuji.
- Pengujian OCR tiruan memeriksa: lokal bersih tanpa API, mini cukup tanpa Sol, perbaikan mini independen, Sol hanya crop terkait, penggabungan tanpa mengganti bagian lain, sinyal ragu, transkripsi rusak, operator rumus dan posisi angka, batas dua Sol per halaman, resume respons mini yang sudah tersimpan setelah kuota gagal, serta larangan eskalasi mahal saat gangguan jaringan/kuota.
- Tes integrasi tiga halaman memastikan halaman tengah yang belum lolos tidak aktif, halaman lain tetap selesai, preview crop memerlukan admin, hanya halaman yang wajib review perlu dikonfirmasi, dan aktivasi akhir memakai hasil otomatis serta manual yang tepat tanpa OCR ulang.
- Preflight **seluruh 12 halaman SBP** memakai render lokal tanpa OpenAI berhasil. Potongan terlebar vertikal sekitar **20,76% tinggi halaman**. Batas awal di halaman 10 dan sel jadwal gabungan halaman 11 diperbaiki; crop contoh halaman 3 dan 11 diperiksa secara visual, dan regresi sel gabungan ditambahkan.
- Build TypeScript/Vite berhasil. Browser nyata desktop 1440×1100 dan mobile 390×844 pada fixture terpisah: hanya 1 dari 12 halaman wajib review; crop 442 piksel dari halaman 2400 piksel; koreksi tersimpan setelah refresh; polling tidak menghapus draft; setelah satu halaman dikonfirmasi tombol indeks tersedia tanpa konfirmasi 11 halaman otomatis. Tidak ada error JavaScript atau overflow horizontal. Fixture tidak diaktifkan atau dicampurkan ke KB demo; tidak ada request OpenAI.
- Instalasi utama direstart dan diperiksa melalui browser: admin/health normal, satu dokumen aktif (Perpol), SBP tetap menunggu review. Migrasi mempertahankan draft manual, melepas kewajiban konfirmasi tiga draft AI yang cocok dengan cache. Tampilan kini **0/9 halaman wajib review**; angka ini bukan klaim sembilan halaman salah, melainkan sembilan belum dikonfirmasi/lolos. Tidak ada konfirmasi manusia yang dipalsukan.
- Worker versi **82503cf1-fb04-4902-aafb-8f9b54fefe40** dideploy dengan batas 2 juta unit dan expiry lama. Smoke `/vision-fragment`: tanpa token **401**, dengan token **429 relay_budget**. Permintaan berhenti sebelum OpenAI; **belum ada hasil GPT-5.6 Sol nyata**. Kuota tidak dinaikkan atau dilewati memakai counter lain. Akurasi pipeline baru dan kelanjutan ingestion SBP masih menunggu kuota yang memadai dan evaluasi berbayar.

## Uji berbayar terbatas setelah persetujuan pengguna

Pada 8 Oktober 2026 pengguna mengizinkan uji berbayar dengan pemakaian kecil. Uji berhenti setelah **tepat tiga request OpenAI**, tanpa retry otomatis: dua GPT-4.1 mini dan satu GPT-5.6 Sol. Semua melalui relay Cloudflare dan kuota Durable Object yang sama. Batas sementara 2,4 juta unit dipulihkan ke **2 juta** dengan rollback ke `82503cf1-fb04-4902-aafb-8f9b54fefe40`; counter pemakaian tidak direset, expiry/secret tidak diubah. Konfigurasi versi hasil pemulihan diperiksa melalui Wrangler.

Sampel adalah crop pertama PDF SBP halaman 3, sebesar **16,77% tinggi halaman**, yang memuat nomor pengumuman, tanggal tulisan tangan, serta semester. Tesseract lokal menghasilkan confidence rata-rata 90,47. Mini pertama menerima gambar yang diproses lokal, mini kedua gambar asli; Sol hanya menerima crop asli, tanpa hasil OCR sebelumnya. Respons lengkap dan usage disimpan pada direktori lokal yang diabaikan Git, `tmp/paid-sol-test/`; teks sumber tidak ditambahkan ke Git.

| Panggilan | Input / output token | Waktu | Estimasi biaya API |
| --- | --- | --- | --- |
| GPT-4.1 mini, diproses | 1.487 / 112 | 4,116 detik | US$0,0007740 |
| GPT-4.1 mini, asli | 1.487 / 111 | 2,293 detik | US$0,0007724 |
| GPT-5.6 Sol, asli | 1.195 / 175 | 4,216 detik | US$0,0082800 |
| Total | 4.169 / 398 | 10,625 detik tiga request berurutan | **US$0,0098264** |

Semua respons HTTP 200, finish reason `stop`, JSON valid, `uncertain=false`; cached input 0. Output Sol mencakup 43 token reasoning, sudah masuk perhitungan. Biaya dihitung dari usage respons dan tarif standar yang diperiksa pada [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini) serta [GPT-5.6 Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol). Sekitar **Rp167** dengan asumsi ilustrasi Rp17.000/US$, bukan kurs kartu terverifikasi; belum termasuk pajak/biaya lain. Waktu adalah request relay sampai respons lengkap, bukan waktu chat ataupun ingestion seluruh halaman.

Pemeriksaan visual crop asli: ketiga hasil mempertahankan nomor **23**, tanggal **14 September 2026**, **SMT II T.A. 2025**, dan **SMT I T.A. 2026**. Dua mini sepakat menurut pemeriksa `fragments_agree`, Sol sesuai keduanya. Ada variasi tanda baca/format baris; hasil ini tidak membuktikan transkripsi identik setiap karakter atau akurasi umum.

**Sol dipanggil sebagai pembanding diagnostik yang disengaja**, karena mini sudah sepakat. Uji ini membuktikan akses model nyata, payload crop, format respons, latency, dan biaya sampel; belum membuktikan Sol memperbaiki kasus yang benar-benar gagal pada mini. Tidak ada request tambahan, embedding, aktivasi dokumen, atau konfirmasi review manusia otomatis. SBP tetap belum aktif; pengujian seluruh scan dan eskalasi otomatis pada perbedaan nyata masih belum selesai.

## Tampilan review hanya halaman yang belum selesai

Atas permintaan pengguna, daftar awal review hanya menampilkan halaman wajib review yang belum dikonfirmasi. Halaman pertama dipilih otomatis; setelah konfirmasi tersimpan, halaman keluar dari daftar dan halaman berikutnya dipilih. Tombol **Review seluruh halaman** membuka seluruh halaman, termasuk hasil otomatis dan halaman yang sudah dikonfirmasi. Filter tampilan tidak mengubah persyaratan aktivasi dokumen.

Build TypeScript/Vite lulus. Browser nyata pada fixture terpisah 12 halaman (dua wajib review, sepuluh lolos otomatis) memverifikasi: hanya dua nomor halaman muncul secara default, konfirmasi pertama menyisakan satu halaman dan memilihnya otomatis, mode lengkap memuat 12 halaman, pergantian mode ditahan saat ada draft, polling mempertahankan draft, setelah konfirmasi terakhir daftar kosong dengan petunjuk aktivasi, dan status tersimpan setelah reload. Mode lengkap tetap dapat membuka halaman yang sudah dikonfirmasi. Desktop 1440×1100 dan mobile 390×844 diperiksa secara visual; tanpa overflow horizontal atau error JavaScript. Tidak ada API AI atau aktivasi indeks pada pengujian ini; fixture tidak dicampurkan ke KB utama.

## Penerapan nyata pipeline pada SBP

Setelah izin pengguna, run persisten memakai ulang empat halaman AI yang lolos dan memproses halaman 5–12. Sebanyak 86 request GPT-4.1 mini + 5 Sol selesai, estimasi US$0,1141628; Sol terpicu otomatis pada perbedaan nyata. Sepuluh halaman lolos, halaman 10 dan 12 masih wajib review; SBP belum aktif. Rincian biaya, temuan halusinasi pada crop hampir kosong yang berhasil ditahan, batas anggaran server, hasil verifikasi, serta izin kuota lanjutan ada di [sbp-live-ocr.md](sbp-live-ocr.md).

## Sapaan tanpa peringatan referensi — 8 Oktober 2026

Sapaan dengan nama seperti “halo sira” sebelumnya tidak cocok dengan pola sapaan lokal, sehingga dikirim ke RAG dan jawaban sapaan tanpa sumber ditolak pemeriksa referensi. Pola kini menerima nama SIRA sebelum/setelah sapaan serta tanda baca umum, dengan pencocokan seluruh pesan. Pesan gabungan seperti “Halo Sira, apa persyaratan pendidikan SBP?” tetap diproses sebagai pertanyaan dokumen dan tidak dibebaskan dari pemeriksaan sumber.

Empat tes regresi sapaan/referensi lulus dengan AI palsu, termasuk tidak ada panggilan embedding/jawaban pada sapaan, konteks topik sebelumnya tetap utuh, jawaban faktual tanpa sumber tetap ditolak, dan retry referensi tetap berjalan. Ruff lulus. Run awal di sandbox tidak selesai dan dihentikan; rerun runtime lokal lulus, dengan satu peringatan deprecation TestClient/httpx yang sudah ada.

Backend utama direstart saat dua dokumen berstatus siap. Browser desktop 1440×1000 dan mobile 390×844 menampilkan balasan lokal “Saya SIRA” untuk “halo sira”, tanpa peringatan, referensi palsu, atau error JavaScript. Screenshot lokal di `tmp/greeting-ui/` diabaikan Git. Tidak ada panggilan OpenAI pada verifikasi sapaan ini.

## Riwayat dan konteks persisten — 8 Oktober 2026

Atas keputusan terbaru pengguna, refresh/tutup browser/restart aplikasi tidak lagi menghapus percakapan. SQLite schema 5 menyimpan hash token sesi, pertanyaan terdahulu untuk maksud follow-up, konteks pencarian, pesan, referensi, serta status jawaban. Browser hanya menyimpan token acak di localStorage untuk origin tersebut. Riwayat dipulihkan melalui endpoint POST yang memerlukan token sesi dan memeriksa origin; isi riwayat tidak diterima dari klien sebagai konteks model. Jawaban lama tidak menjadi sumber fakta.

Tombol Percakapan baru membuat sesi baru sekaligus menghapus sesi/pesan lama secara transaksional; token lama tidak bisa membaca riwayat atau mengirim pertanyaan lagi. Tab lain mengikuti reset. Sesi tidak kedaluwarsa karena idle; cache memori dapat dikeluarkan dan dimuat ulang tanpa kehilangan data. Perubahan KB tetap memperbarui konteks sumber agar dokumen yang dihapus tidak digunakan kembali, tanpa menghapus pesan yang tampil.

Respons streaming menyimpan progres secara berkala; selesai/error disimpan sebelum event diteruskan. Pembatalan/koneksi terputus mempertahankan teks parsial sebagai belum selesai. Startup menandai respons pending yang terputus. Restore yang gagal tidak membuat sesi kosong secara diam-diam; UI menyediakan Muat ulang riwayat. Restore pending melakukan polling lokal dan tidak mengulang panggilan model.

Verifikasi:

- Seluruh suite backend: 40 lulus, 1 live opt-in dilewati. Setelah penguncian cache sesi dan tes pembatalan stream ditambahkan, 8 tes regresi terkait diulang dan lulus. Satu peringatan deprecation TestClient/httpx yang sudah ada. Ruff lulus. Tes memakai AI palsu.
- Tes membuktikan riwayat/referensi dan follow-up bertahan setelah pengeluaran cache serta app baru; konteks tetap hanya pertanyaan terdahulu. Browser lain tidak dapat melihat riwayat tanpa token. Token lama dicabut setelah reset. Gangguan stream dan restart mempertahankan jawaban parsial tanpa menjadikannya konteks fakta. Pemeriksaan sumber dan sapaan tetap lulus.
- Build TypeScript/Vite lulus; run awal dibatasi realpath Windows pada sandbox, rerun lokal berhasil. Tidak ada perubahan Worker atau deployment Cloudflare untuk fitur ini.
- Browser nyata pada aplikasi utama: refresh, navigasi admin/kembali, tutup/buka tab, lalu browser/backend restart memulihkan dua pesan sapaan. Gangguan endpoint history simulasi tidak mengganti token/menghapus riwayat; retry memulihkan pesan. Percakapan baru mengosongkan pesan, mencabut token lama (410), memperbarui tab kedua, dan tetap kosong setelah refresh. Konteks browser terpisah tetap kosong. Desktop/mobile tidak mengalami error JavaScript atau overflow horizontal. Semua verifikasi UI memakai sapaan lokal, tanpa panggilan OpenAI.

Bukti lokal di `tmp/persistent-chat-ui/`, diabaikan Git. Pemulihan menggunakan browser/profil dan origin yang sama; penghapusan data situs menghilangkan penanda sesi. Tidak ada daftar percakapan lama atau sinkronisasi antarperangkat dalam prototype ini.

## Cadangan penanda sesi saat refresh — 8 Oktober 2026

Pengguna melaporkan riwayat kosong setelah refresh. Pemeriksaan read-only menunjukkan percakapan pengguna masih tersimpan (18 pesan), tanpa kehilangan data SQLite. Pengguna mengonfirmasi Chrome/Edge pada http://127.0.0.1:8000. Penyebab spesifik pada browser pengguna belum terverifikasi: alat inspeksi browser tidak dapat dimulai karena kernel assets tidak tersedia. Salah satu kemungkinan ialah tab masih menjalankan bundle sebelum implementasi persistence saat pertanyaan dikirim; backend baru menyimpan pesan, tetapi frontend lama belum menyimpan token. Jangan menyatakan localStorage atau bundle lama pasti menjadi penyebab laporan tersebut.

Kelemahan yang diperbaiki: versi sebelumnya hanya mencoba restore jika penanda localStorage tersedia. Kini UI selalu memeriksa sesi server saat boot. Pembuatan/pemulihan sesi juga memasang cookie `sira_chat` HttpOnly/SameSite Strict pada `/api/chat` sebagai cadangan. Local token yang valid dapat memasang cookie untuk instalasi lama; cookie dapat memulihkan token localStorage yang hilang. Token yang diberikan secara eksplisit tetap harus valid; cookie tidak menyamarkan token salah/dicabut. Tanpa kedua kredensial, server tidak menebak percakapan terakhir atau membagikan riwayat browser lain. Reset dengan penanda lokal kosong tetap mencabut sesi yang dibuktikan cookie.

Cookie juga dipasang pada setiap respons chat valid, agar tab lama yang masih membawa token dalam memori memperoleh cadangan meskipun belum menjalankan bootstrap frontend baru. 10 tes regresi backend lulus (cookie, halaman lama, isolasi, origin, reset, konteks/history, sapaan, referensi, pembatalan stream); Ruff dan build UI lulus. Browser nyata memverifikasi penanda lokal dihapus lalu refresh memulihkan pesan yang sama, migrasi local-token ke cookie, buka ulang dengan cookie saja, localStorage get/set sengaja diblokir, reset tetap kosong setelah refresh, token lama 410, dan browser terpisah kosong. Tanpa error JavaScript atau panggilan AI. Peringatan penyimpanan hanya ditampilkan bila cadangan cookie tidak dapat dikonfirmasi, sehingga localStorage yang diblokir dengan cookie valid tidak dianggap kehilangan sesi. Bukti `tmp/chat-cookie-ui/` diabaikan Git. Riwayat pengguna tidak dihapus atau dipilih sebagai fallback global. Hasil pada browser pengguna masih menunggu konfirmasi.


## OCR layout-v3: gambar mandiri, antrean dan sel gabungan — 8 Oktober 2026

Alur produksi memakai DocumentOCR, bukan pembagian tetap enam band. Producer lokal menyimpan rencana seluruh halaman tanpa menunggu AI. Tiga worker membaca area dari piksel render asli; OCR lokal dan transkripsi model lain tidak pernah masuk payload vision. Gambar tabel tetap utuh. Structured Outputs mencatat sel kosong, header, rowspan/colspan dan status ragu. Validasi lokal memeriksa grid lengkap dan hubungan sel terhadap garis sumber. Hasil yang belum lolos setelah Sol menjadi review selektif; review seluruh halaman tetap tersedia.

Verifikasi akhir:

- Backend: 55 lulus, 1 tes live opt-in dilewati, 44,75 detik. Ruff lulus. Peringatan deprecation TestClient/httpx yang sudah ada tetap muncul. Tes regresi mencakup producer lima halaman selesai saat tiga worker AI masih menunggu, input gambar asli tanpa transkripsi, crop tabel utuh, resume tanpa pengulangan mini, selective review, aktivasi atomik, dan konteks “masa sih?” dari pertanyaan user terdahulu.
- Geometri: scan sintetis dengan garis samar, sedikit kemiringan, dan tepi halaman gelap mempertahankan sel gabungan; catatan di samping tabel tidak dibuang. Struktur tabel salah meskipun AI menyatakan yakin ditolak. Sel kosong tidak mengambil nilai baris sebelumnya, dan record kegiatan/tanggal tidak terpisah saat chunking.
- Relay: type check, 8 tes policy/biaya dan 10 tes runtime lulus. Payload tidak dapat mengirim model, prompt, atau teks OCR sendiri; format layout memakai JSON schema ketat. Deploy Cloudflare versi ad839ddc-1769-4b63-92ce-ff7f1aaf2cbf, cumulative caps tetap dinonaktifkan sesuai keputusan pemilik. Rate/auth/expiry tetap berlaku.
- Frontend: build TypeScript/Vite lulus. Browser desktop/mobile pada API fixture memeriksa tombol Baca ulang dengan AI untuk dokumen aktif, progres dua antrean, default satu halaman wajib review dari 12, opsi semua halaman, dan tanpa overflow/error JavaScript. Fixture tidak mengubah knowledge base utama.
- Pemeriksaan lokal SBP 12 halaman berlangsung 46,75 detik pada komputer ini. Rencana akhir diverifikasi ulang tanpa API: 16 area pembacaan awal, dua tabel (19×4 dan 7×4 termasuk header). Ini bukan benchmark waktu total dengan AI atau estimasi jumlah fallback.

Uji berbayar dibatasi empat request, bukan ingestion ulang seluruh dokumen: mini halaman penuh, dua crop Sol, dan mini tabel utuh. Estimasi total US$0,0391808 berdasarkan usage API dan tarif worker/src/cost.ts. Uji awal menemukan koordinat perkiraan mini tidak cocok dengan gambar; crop kini menggunakan geometri lokal dan posisi kata sumber. Mini juga melewatkan satu baris tabel meskipun menyatakan yakin; hasil tersebut ditolak validator. Respons Sol tabel utuh tervalidasi terhadap geometri akhir, dengan tanggal kep kelulusan/kirim surat panggil 23–26 November 2026, terpisah dari kirim berkas 29 Oktober 2026. Tulisan tangan/header pada pembacaan halaman penuh masih meminta review.

Dokumen aktif utama tidak diproses ulang atau dikonfirmasi otomatis. Baca ulang dengan AI membuat versi pending dari file persisten, mempertahankan versi aktif sampai embedding dan aktivasi versi baru berhasil. Untuk memakai struktur tabel baru pada SBP lama, admin menjalankan tindakan itu dan menyelesaikan review jika diminta. Bukti lokal tersimpan di tmp/ocr-v3/ (diabaikan Git), termasuk respons mentah uji berbayar, rencana, durasi dan tangkapan UI. Deteksi layout tetap heuristik; akurasi seluruh dokumen dan durasi total ingestion pipeline baru belum diuji berbayar.


## Regresi false positive review 12/12 — 8 Oktober 2026

Pemeriksaan data nyata menunjukkan halaman 1–10 ditolak akibat validator: pencocokan kata umum mencakup hampir seluruh halaman, perbandingan critical signature mencampur angka antarblock, nomor halaman yang tidak ditranskripsikan dianggap ketentuan hilang, dan rows nonzero pada block text tanpa cells dianggap tabel. Tidak ada panggilan Sol pada sepuluh halaman itu karena area hasil pencocokan terlalu besar.

Perbaikan memakai urutan frasa untuk lokasi, membandingkan bukti angka satu kali pada area sumber yang sama (confidence lokal minimal 95 untuk angka), dan tetap memeriksa negasi/semester. Folio terpisah tidak dihitung sebagai syarat/tanggal; nomor halaman PDF tetap tersimpan. Keraguan Sol yang sudah ada tidak dibuang hanya karena mini kini lolos validator; hasil final tersimpan dipertahankan tanpa duplikasi. Validator diberi revisi agar draft lama dapat dievaluasi ulang memakai respons yang sudah dibayar.

Uji salinan kemudian pemulihan SQLite utama dari respons asli tersimpan: 10 halaman lolos, halaman 11–12 wajib review hanya pada nomor pengumuman di header yang hasil Sol-nya masih uncertain. Kedua tabel lolos. Nol request AI tambahan; tidak ada embedding/aktivasi baru atau konfirmasi manusia otomatis. Dua KB aktif dan revision 4 dipertahankan, server kembali sehat. Backup serta bukti lokal berada di tmp/ocr-review-fix/ yang diabaikan Git. Edit admin dengan revision positif dipertahankan.

Tes regresi mencakup kata berulang, tanggal antarparagraf, angka lokal lemah dibanding vision jelas, perubahan tahun yang terbaca kuat, negasi, folio dibanding tanggal sungguhan, serta resume Sol tanpa pengulangan request/duplikasi teks. Tes OCR terarah: 14 lulus. Seluruh backend: 59 lulus, 1 live opt-in dilewati; Ruff lulus. Tidak ada perubahan Worker/frontend dalam perbaikan ini. Ambang confidence dan pencocokan layout tetap heuristik; pemeriksaan otomatis tidak menjamin seluruh fakta benar.


## Petunjuk review dan verifikasi PDF campuran — 8 Oktober 2026

Admin memperoleh alasan dan kutipan spesifik, penanda area perkiraan pada gambar, crop per hint serta seleksi teks pada editor. Kutipan/posisi berasal dari respons AI dan bukti lokal tersimpan, bukan request baru. Sel tabel menyebut row/column dan grid lokal dapat menentukan crop sesuai rowspan/colspan. Lokasi yang tidak dapat diketahui karena format AI gagal dijelaskan sebagai kegagalan format, bukan dugaan kata salah. Draft transkripsi dari respons berbayar yang gagal koordinat kini dipertahankan untuk review, tetap belum diterima sebagai KB.

65 tes backend lulus, 1 live opt-in dilewati (35,12 detik); Ruff dan build TypeScript/Vite lulus. Tes mencakup koordinat relatif crop Sol, whitespace/ambiguitas kutipan, merged-cell hint, kegagalan format tanpa penanda palsu, draft berbayar yang tidak dibuang, crop hint/auth/stale-version serta dokumen native+image dua halaman: hanya halaman gambar memanggil OCR, tanpa AI untuk teks/scan lokal bersih. Setelah perapian terakhir, 5 tes petunjuk diulang dan lulus, termasuk penyempitan lokasi perkiraan model berdasarkan frasa pada gambar sumber.

Browser desktop/mobile memakai fixture dari hasil review terbaru (tanpa kredensial/admin asli): halaman 12 menampilkan kutipan nama pejabat/pangkat, crop tanda tangan dan seleksi editor; nomor/teks ragu tidak dinyatakan salah otomatis. Penanda gambar, scroll editor dengan wrapping mobile, edit belum tersimpan saat polling, penolakan lokasi fiktif pada format error, serta tanpa overflow/error JavaScript lulus. Visual desktop/mobile diperiksa. Bukti di tmp/review-hints/; nol request berbayar dan tidak ada modifikasi/konfirmasi/aktivasi dokumen utama.

SBP terbaru saat pemeriksaan memiliki tiga halaman wajib review (2,3,12), berbeda dari versi terdahulu yang telah diganti pengguna. Halaman 2–3 menyimpan format_error koordinat; kata tertentu belum dapat dilokalisasi dari respons yang tersedia. Halaman 12 menyimpan uncertain pada nama pejabat/pangkat; crop pada gambar cocok dengan bagian tersebut. File upload byte-identik dengan SBP asli di workspace: 12 halaman, satu gambar memenuhi tiap halaman, nol karakter native menurut pdfplumber dan PDFium. Tidak ada aturan yang mengasumsikan halaman 2–5 saja scan, dan tidak ada perubahan isi dokumen atau hardcode khusus SBP.

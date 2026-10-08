# Implementation Plan - SIRA

Status: implementasi prototype berjalan setelah persetujuan pengguna. Fondasi, UI, ingestion, retrieval, relay, dan tes lokal tersedia; evaluasi OpenAI nyata serta akurasi bahan resmi masih berlangsung. Lihat `task.md` dan `docs/testing.md` untuk bukti progres.

Tanggal penyusunan: 8 Oktober 2026.

## 1. Tujuan dan pedoman

Membangun **SIRA - Asisten Informasi SDM Polri**, prototype chatbot Retrieval-Augmented Generation (RAG) yang menjawab berdasarkan dokumen yang dimasukkan admin. Aplikasi dapat dijalankan secara lokal oleh penguji, dengan layanan OpenAI melalui relay Cloudflare Workers milik peserta.

Pedoman tugas:

- `Soal RAG.pdf`, terutama kebutuhan aplikasi dan perilaku jawaban pada halaman 2-3.
- `Paparan Uji Pemrograman.pdf`, terutama kemampuan RAG dan keluaran seleksi tahap 2 pada halaman 5-6.
- Masa pengerjaan tugas: 8-14 Oktober 2026.

Bahan knowledge base untuk pengujian:

- `PERPOL NO 1 TAHUN 2025.pdf`: dokumen peraturan terkait penilaian kinerja/SIPK, memiliki lapisan teks; tabel dan rumus tetap perlu diperiksa.
- `PENGUMUMAN SBP TA 2027.pdf`: dokumen pengumuman seleksi, berupa scan dan membutuhkan OCR; ukuran sekitar 52 MB.

Kedua dokumen pedoman tidak otomatis menjadi knowledge base. Instalasi baru dimulai dengan knowledge base kosong; dokumen contoh dimasukkan melalui admin saat demo.

## 2. Keputusan ruang lingkup

### Masuk prototype

- Satu halaman chat dengan riwayat sesi, kolom pertanyaan, tombol kirim, dan tombol percakapan baru.
- Halaman admin terpisah dengan satu akun admin.
- Upload PDF teks maupun scan, maksimum 100 MB per dokumen, divalidasi di backend.
- Tambah dokumen, ubah metadata, ganti file dokumen, dan hapus dokumen.
- Penyimpanan persisten untuk PDF, hasil ekstraksi, metadata, serta embedding/index.
- Pipeline parsing, OCR bila diperlukan, chunking, embedding, retrieval, dan generasi jawaban.
- GPT-4o mini sebagai satu-satunya model jawaban. OCR: lokal → GPT-4.1 mini → GPT-5.6 Sol hanya pada potongan yang masih meragukan (keputusan pengguna 8 Oktober 2026).
- Konteks dan riwayat satu percakapan persisten untuk pertanyaan lanjutan; dipulihkan saat refresh/buka ulang dan dihapus hanya melalui Percakapan baru (keputusan pengguna 8 Oktober 2026).
- Jawaban sopan dan profesional, disertai referensi dokumen berupa teks biasa.
- Jawaban streaming dan penanganan kesalahan yang dapat dipahami pengguna.
- Proteksi berlapis terhadap prompt injection, penyalahgunaan API, dan akses admin tanpa izin.
- Dokumentasi API, README, bukti pengujian, serta panduan demo/video.
- Review gambar asli dan koreksi teks per halaman oleh admin, ditambahkan atas permintaan pengguna 8 Oktober 2026. Draft review lokal tidak menggunakan OCR AI; konfirmasi diwajibkan hanya pada halaman yang belum lolos atau diedit admin sebelum indeks dibuat dan versi diaktifkan.

### Pengembangan lanjutan, belum diimplementasikan

- Pemilihan model atau provider AI oleh admin dan pengisian API key melalui UI.
- Klasifikasi dokumen publik/rahasia dan hak akses dokumen per pengguna.
- Daftar beberapa percakapan, sinkronisasi riwayat antarperangkat, akun pengguna umum, dan pengelolaan banyak admin.
- Dukungan format selain PDF, deployment aplikasi penuh ke cloud, dan sinkronisasi knowledge base antar-PC.

Tidak ada link PDF atau fasilitas download dokumen untuk pengguna chat. Tanpa klasifikasi/hak akses dokumen, seluruh isi knowledge base aktif berpotensi dijawab oleh SIRA; referensi non-clickable tidak membatasi pengungkapan isi melalui jawaban.

## 3. Tech stack

| Bagian | Teknologi | Tanggung jawab |
| --- | --- | --- |
| Frontend | React, TypeScript, Vite, CSS | UI chat dan admin yang rapi serta responsif |
| Backend lokal | Python, FastAPI, Uvicorn | API, autentikasi, ingestion, retrieval, percakapan, penyajian hasil build frontend |
| Data aplikasi | SQLite | Akun admin, metadata dokumen, halaman, teks ekstraksi, status pekerjaan, riwayat/konteks percakapan |
| Vector database | ChromaDB dengan PersistentClient | Embedding dan pencarian kemiripan lokal |
| File dokumen | Folder data lokal di luar aset publik frontend | PDF asli dan artefak pemrosesan yang diperlukan |
| Ekstraksi PDF | pdfplumber | Ekstraksi teks per halaman dan bantuan pembacaan struktur/tabel |
| Render PDF | pypdfium2 | Render halaman scan menjadi gambar untuk OCR |
| OCR lokal | Tesseract, bahasa Indonesia dan Inggris | Ekstraksi teks scan; kualitas dibuktikan pada bahan uji |
| Preprocessing | Pillow/OpenCV sesuai kebutuhan | Rotasi, deskew, kontras, dan penyesuaian gambar tanpa mengubah substansi |
| Tokenisasi | tiktoken | Pengukuran ukuran chunk dan anggaran konteks |
| Model jawaban | OpenAI GPT-4o mini | Jawaban berbasis evidence |
| OCR AI | GPT-4.1 mini, fallback GPT-5.6 Sol | Mini memeriksa scan; Sol hanya potongan yang masih meragukan |
| Model embedding | OpenAI text-embedding-3-small | Embedding chunk dan pertanyaan |
| Relay AI | Cloudflare Workers, TypeScript, Secrets | Menjaga API key OpenAI di server dan membatasi permintaan AI |
| Streaming | HTTP streaming/SSE | Mengirim respons bertahap sampai UI |
| Dokumentasi API | OpenAPI dan Swagger UI FastAPI | API yang dapat diperiksa penguji |

Versi dependensi dipastikan kompatibel pada Windows lalu dikunci saat tahap setup. Tidak memasang atau memperbarui paket hanya untuk menyusun rencana ini.

Pipeline RAG disusun secara eksplisit agar mudah diperiksa dan dijelaskan saat wawancara. Tidak memerlukan framework orkestrasi tambahan untuk alur awal.

## 4. Arsitektur dan batas lokal/cloud

```text
Browser lokal
  |-- Halaman chat
  |-- Halaman admin
  |
FastAPI lokal
  |-- SQLite: akun, dokumen, halaman, hasil ekstraksi, pekerjaan ingestion
  |-- Folder data: PDF asli dan hasil pemrosesan
  |-- ChromaDB persisten: chunk, embedding, metadata sumber
  |-- Pipeline ingestion dan retrieval
  |
Cloudflare Worker milik peserta
  |-- Autentikasi akses pengujian, batas penggunaan, validasi operasi/model
  |-- API key OpenAI melalui Secrets
  |
OpenAI: embedding, GPT-4o mini untuk chat, GPT-4.1 mini dan fallback GPT-5.6 Sol untuk OCR
```

- UI dan backend aplikasi dijalankan pada localhost; hasil build React dilayani FastAPI agar penguji tidak perlu menjalankan server frontend terpisah.
- Node.js diperlukan untuk membangun ulang frontend. Alur penggunaan hasil build cukup menjalankan backend melalui petunjuk/launcher yang disiapkan.
- PDF dan vector database tersimpan lokal. Teks chunk saat embedding, konteks relevan saat menjawab, serta gambar halaman yang membutuhkan bantuan vision dikirim ke layanan AI melalui Worker.
- Internet diperlukan untuk fungsi AI. Jika koneksi gagal, dokumen tetap tersimpan dan UI memberi pesan kegagalan yang jelas.
- API key OpenAI tidak dimasukkan ke source, hasil build, database lokal, atau paket yang dibagikan kepada penguji.
- Kredensial akses relay yang tersedia pada PC penguji dapat diperiksa pemilik PC; perlindungannya berupa kuota, pembatasan operasi, pencabutan, dan masa berlaku di server, bukan klaim bahwa token lokal tidak dapat diambil.
- Tidak memerlukan VPS, Supabase, Redis, atau layanan database cloud untuk ruang lingkup awal.

## 5. Penyimpanan dan konsistensi dokumen

Struktur awal yang direncanakan:

```text
backend/                 API dan pipeline Python
frontend/                React/TypeScript dan hasil build
worker/                  Relay Cloudflare
data/app.sqlite3         Data aplikasi lokal
data/documents/           PDF dengan nama internal yang aman
data/chroma/              Vector database persisten
data/processing/          File sementara pekerjaan ingestion
tests/                   Pengujian terarah dan bahan evaluasi
docs/                    Arsitektur, hasil evaluasi, dan panduan demo
README.md
implementation_plan.md
task.md                  Checklist progres dan bukti penyelesaian
```

Lokasi data dibuat stabil meskipun aplikasi diluncurkan dari direktori lain. Database, file upload, cache, token, dan hasil build yang tidak diperlukan tidak ikut dipublikasikan ke Git.

Data minimum:

- Admin: identitas, password hash, dan metadata sesi autentikasi bila diperlukan.
- Dokumen: ID, judul tampilan, nama asli, path internal, hash file, ukuran, jumlah halaman, versi aktif, status, waktu proses, dan pesan kesalahan/peringatan.
- Halaman: nomor halaman PDF, teks, metode ekstraksi, peringatan kualitas, dan versi dokumen.
- Chunk: ID stabil, ID/versi dokumen, halaman sumber, penanda bagian bila tersedia, teks, serta informasi model embedding.
- Pekerjaan ingestion: status, progres, tahap terakhir, dan informasi kegagalan yang aman.

Aturan lifecycle:

- Status awal: `processing`; setelah berhasil: `ready`; jika gagal: `failed`, dengan alasan yang dapat dipahami admin.
- Chat hanya mengambil chunk milik versi dokumen yang berstatus aktif dan siap.
- Mengganti file membuat versi baru; versi lama tetap dapat dipakai sampai versi baru berhasil diproses. Jika gagal, versi lama tetap aktif dan kegagalan penggantian terlihat di admin.
- Menghapus dokumen langsung mengeluarkannya dari retrieval, lalu membersihkan chunk, file, dan cache terkait. Kegagalan pembersihan dapat diulang.
- SQLite dan Chroma tidak memiliki satu transaksi bersama; gunakan versioning, aktivasi setelah seluruh tahap berhasil, dan pembersihan idempoten untuk mencegah indeks setengah jadi.
- Pekerjaan yang terputus saat aplikasi ditutup ditandai saat startup, dengan mekanisme proses ulang. Data siap yang sudah ada tidak di-embedding ulang setiap startup.
- Tahap awal menggunakan satu antrean ingestion lokal dan eksekusi OCR di proses/thread kerja yang sesuai agar request chat tidak tertahan pekerjaan CPU.

## 6. Ingestion, OCR, dan chunking

Urutan pemrosesan:

1. Validasi ukuran, format PDF sebenarnya, keterbacaan, enkripsi/password, serta batas sumber daya pemrosesan.
2. Simpan file secara aman, hitung hash, buat versi dan pekerjaan ingestion.
3. Ekstrak teks per halaman. PDF campuran diputuskan per halaman, bukan berdasarkan seluruh file.
4. Untuk halaman scan atau ekstraksi yang tidak memadai, render gambar dengan resolusi yang sesuai, lakukan preprocessing yang diperlukan, lalu jalankan OCR lokal.
5. Tentukan bagian yang membutuhkan bantuan AI menggunakan gabungan sinyal: teks kosong/terlalu sedikit, karakter rusak, confidence OCR, tata letak sulit, tabel, dan ketidaksesuaian hasil ekstraksi.
6. Kirim potongan meragukan ke GPT-4.1 mini melalui Worker. Pembacaan kedua mini dilakukan jika perlu; GPT-5.6 Sol menjadi opsi terakhir hanya untuk potongan yang masih berbeda/ragu, maksimal dua potongan per halaman. Batas crop menjaga baris dan sel tabel; detail ada pada `docs/ocr-fallback.md`. Instruksikan transkripsi setia sumber tanpa mengisi isi yang hilang.
7. Jika hasil tetap tidak terbaca atau perbedaan kritis belum terselesaikan, tampilkan peringatan/kegagalan yang jujur. Jangan mengaktifkan versi sebagai knowledge base siap jika halaman penting belum berhasil diproses.
8. Simpan teks, asal halaman, metode ekstraksi, dan peringatan. Hilangkan header/footer berulang secara hati-hati tanpa membuang makna pasal atau persyaratan.
9. Pecah teks berdasarkan struktur bagian/pasal/persyaratan, lalu batas token. Pertahankan hubungan butir, negasi, angka, dan header tabel.
10. Buat embedding secara batch, simpan ke Chroma, validasi kelengkapan, lalu aktifkan versi dokumen.

Parameter awal untuk eksperimen, bukan nilai final yang sudah terbukti: chunk sekitar 500-800 token, overlap sekitar 80-120 token. Kalibrasi menggunakan kedua bahan uji; tabel atau ketentuan yang saling terkait tidak dipotong sembarangan.

Confidence OCR dan kecocokan dua mesin bukan jaminan benar. Hasil scan perlu diperiksa terhadap gambar sumber, terutama pangkat, pendidikan, angka, tanggal, syarat, dan kata negasi. Permintaan pengguna pada 8 Oktober 2026 memperluas prototype dengan review dan koreksi per halaman: preview hanya untuk admin, draft persisten, penolakan edit dari tab lama, dan aktivasi setelah embedding berhasil. Pembaruan berikutnya pada hari yang sama membatasi konfirmasi wajib pada halaman/bagian yang belum lolos atau diedit; halaman lolos otomatis tidak perlu dikonfirmasi ulang.

Keterangan wajib di admin:

> **Perhatian terhadap akurasi OCR**
>
> Ekstraksi dokumen scan dapat menghasilkan kesalahan, terutama pada angka, tabel, dan kata yang memengaruhi makna ketentuan. Pemeriksaan hasil OCR tetap diperlukan sebelum penggunaan operasional.
>
> **Review oleh admin:** gunakan Review dan koreksi pada dokumen yang belum lolos; pilih potongan yang ditandai, cocokkan gambar asli dan teks, lalu konfirmasi halaman yang memerlukan review sebelum membuat indeks. Halaman yang sudah lolos otomatis tidak wajib dikonfirmasi ulang.

Review dan koreksi merupakan fitur aktif. Penyiapan draft memakai hasil yang sudah tersedia dan OCR lokal, tanpa API vision. Embedding hasil review tetap menggunakan layanan AI berbayar. Status pemrosesan dan peringatan yang benar-benar dihasilkan pipeline tetap ditampilkan.

## 7. Retrieval dan percakapan

Alur pertanyaan normal:

1. Validasi pesan dan ambil riwayat sesi yang relevan dengan batas token.
2. Bentuk pertanyaan pencarian mandiri bila pengguna memakai rujukan seperti "kalau SMA?". Gunakan konteks topik sebelumnya; panggilan AI tambahan hanya bila diperlukan. Jika ambigu, minta klarifikasi dengan sopan.
3. Buat query embedding melalui Worker dan OpenAI.
4. Cari kandidat chunk di Chroma dengan pembatasan versi dokumen aktif.
5. Periksa relevansi, susun konteks secukupnya, dan pertahankan metadata sumber. Nilai similarity bukan probabilitas kebenaran; ambang dikalibrasi lewat evaluasi.
6. Kirim pertanyaan, konteks sumber, dan riwayat yang dibatasi ke GPT-4o mini melalui Worker.
7. Teruskan jawaban streaming sampai UI. Referensi diformat aplikasi dari metadata yang valid, bukan menerima path/link hasil karangan model.
8. Catat metrik latensi tanpa merekam isi dokumen/chat secara default.

Ketentuan jawaban:

- Sopan, profesional, dan berbahasa Indonesia; tidak meniru slang atau kata kasar pengguna.
- Jawaban substansial harus ditopang dokumen yang ditemukan. Jangan mengambil pengetahuan umum model sebagai pengganti sumber yang tidak tersedia.
- Riwayat dipakai untuk memahami maksud, bukan bukti faktual; jawaban terdahulu tidak otomatis dianggap benar.
- Pertanyaan yang memerlukan daftar lengkap harus diuji agar tidak dijawab dari potongan parsial tanpa penjelasan batasnya.
- Jika sumber berbeda ketentuan, jelaskan perbedaan, cakupan, dan sumbernya. Jangan otomatis menetapkan yang paling baru sebagai ketentuan berlaku tanpa dukungan dokumen.
- Referensi berupa teks: nama dokumen, halaman PDF, serta pasal/bagian bila tersedia. Nomor halaman PDF menjadi acuan dasar; nomor cetak dapat ditambahkan bila dapat dipetakan dengan benar.
- Tidak menyediakan tautan, path internal, atau download dokumen.

Contoh ketika informasi tidak tersedia:

> Maaf, informasi tersebut belum ditemukan dalam dokumen yang tersedia. Silakan perjelas pertanyaan atau hubungi pihak yang berwenang untuk memperoleh kepastian.

Contoh ketika ketentuan berbeda:

> Terdapat perbedaan ketentuan dalam dokumen yang tersedia. [Jelaskan perbedaan beserta nama dokumen dan halaman.] Berdasarkan informasi tersebut, saya belum dapat memastikan ketentuan yang berlaku untuk situasi Anda.

Contoh sapaan awal:

> Selamat datang. Saya SIRA, Asisten Informasi SDM Polri. Silakan ajukan pertanyaan mengenai informasi dalam dokumen yang tersedia.

Jika knowledge base kosong, tampilkan sapaan dan pemberitahuan bahwa belum ada dokumen tersedia. Sapaan dan pemberitahuan ini tidak memanggil AI.

Sesi chat:

- Riwayat dan konteks disimpan di SQLite, dipulihkan saat refresh, buka ulang browser yang sama, serta restart aplikasi. Browser menyimpan token sesi acak pada localStorage dan cookie HttpOnly/SameSite Strict sebagai cadangan; hash token dipakai di backend. Saat boot, UI selalu memeriksa sesi server walaupun localStorage kosong.
- Tombol Percakapan baru menghapus pesan/konteks sesi lama dan mencabut token lama. Reset diterapkan pada tab lain dalam browser yang sama melalui perubahan penanda sesi.
- Tidak ada kedaluwarsa percakapan karena idle. Cache objek sesi dapat dikeluarkan dari memori dan dimuat ulang dari database tanpa kehilangan konteks. Riwayat jawaban model tidak diteruskan sebagai sumber fakta; hanya pertanyaan terdahulu yang dipakai untuk memahami maksud.
- Jawaban yang terputus tetap tersimpan sebagai belum selesai; pemulihan riwayat tidak memanggil model ulang. Kegagalan memuat riwayat tidak diam-diam membuat sesi kosong.
- Menghapus dokumen juga mencegah konteks dokumen lama dipakai kembali pada giliran berikutnya; riwayat tidak boleh menghidupkan sumber yang sudah dihapus.

## 8. UI dan keamanan

UI sederhana, rapi, dengan warna navy/putih dan aksen emas secukupnya. Prioritasnya keterbacaan, feedback status, dan fungsi yang dapat didemokan.

Admin menyediakan login, daftar dokumen, form upload, edit metadata, ganti file, hapus dengan konfirmasi, status/progres, alasan kegagalan, peringatan OCR, dan penjelasan fitur pengembangan. Tidak ada kolom API key pada prototype.

Kontrol minimum:

- Password admin di-hash dengan algoritma yang sesuai; ditetapkan saat setup, tidak dibagikan sebagai password tetap di repository.
- Endpoint admin dilindungi di backend, tidak hanya disembunyikan di UI. Sesi menggunakan cookie HttpOnly, pengaturan same-site/origin dan CSRF yang sesuai; Secure digunakan pada deployment HTTPS.
- Bind localhost secara default; jangan membuka akses LAN tanpa konfigurasi yang disengaja.
- API key OpenAI disimpan di Cloudflare Secrets, tidak dikembalikan ke client atau log.
- Worker membatasi operasi, model, ukuran request, token, frekuensi, total penggunaan, masa berlaku, dan pencabutan akses. Tidak menjadi proxy bebas ke URL/API pilihan pemanggil.
- Konfigurasi produksi dan pengujian tidak menerima arbitrary system prompt dari pengguna chat; backend/relay menetapkan instruksi dan format permintaan yang diperbolehkan.
- Pesan user, riwayat, dan isi dokumen dianggap data tidak tepercaya. Instruksi di dalam dokumen tidak boleh mengganti aturan sistem.
- Chatbot tidak memiliki tool untuk membaca file bebas, mengeksekusi perintah, mengubah knowledge base, atau mengakses rahasia.
- Sanitasi tampilan output dan jangan mengeksekusi HTML model. Referensi harus merujuk sumber retrieval yang valid dan tetap non-clickable.
- Validasi upload, nama/path internal, jumlah halaman/resolusi, serta timeout pemrosesan untuk mengendalikan penggunaan sumber daya.
- Pesan error tidak membocorkan stack trace, token, path rahasia, atau kredensial. Log redaksi data sensitif secara default.

Tidak mengklaim kebal jailbreak. Pertahanan harus dibuktikan melalui uji pesan langsung, serangan lewat dokumen, dan serangan beberapa giliran.

## 9. Kecepatan dan keandalan

- Ukur waktu query embedding, retrieval lokal, waktu sampai teks pertama, dan total jawaban.
- Catat kondisi koneksi serta apakah ada panggilan tambahan untuk resolusi konteks.
- Pertanyaan normal biasanya membutuhkan embedding lalu generasi jawaban secara berurutan; jangan menjanjikan satu panggilan total.
- Pastikan streaming tidak tertahan buffering pada Worker, FastAPI, atau frontend.
- OCR/embedding dokumen hanya saat upload/penggantian, bukan setiap pertanyaan atau startup.
- Cache query embedding yang sesuai secara terbatas; jangan memakai cache jawaban lintas versi knowledge base tanpa invalidasi yang benar.
- Terapkan timeout, retry terbatas dengan backoff untuk operasi yang aman diulang, dan cegah duplikasi pekerjaan ingestion.
- Jika streaming terputus, tandai jawaban tidak selesai; jangan menampilkan pesan parsial sebagai jawaban lengkap.
- Jangan menetapkan klaim waktu respons sebelum mengukur pada lingkungan pengujian.

## 10. Urutan implementasi dan keluaran setiap tahap

Seluruh tahap berikut masih belum dimulai. Implementasi aplikasi dilakukan setelah instruksi pengguna untuk mulai pengerjaan.

| Tahap | Pekerjaan | Keluaran yang harus dapat diperiksa |
| --- | --- | --- |
| 1. Fondasi | Struktur repository, dependensi, konfigurasi, FastAPI, frontend build, database dan setup akun | Aplikasi lokal terbuka, knowledge base kosong, data directory stabil, panduan setup awal |
| 2. Relay AI | Worker, Secrets, kredensial uji, validasi, quota/expiry/revocation, embedding dan streaming | API key tidak tersebar, operasi yang tidak diperbolehkan ditolak, respons dapat diteruskan |
| 3. Ingestion teks | Upload, metadata, parsing per halaman, chunking, embedding, Chroma, status persisten | Dokumen teks siap dicari dan tetap tersedia setelah restart |
| 4. OCR | Render, preprocessing, Tesseract, bantuan vision selektif, peringatan, verifikasi bahan scan | Dokumen scan dapat diindeks dengan hasil kritis diperiksa; batas OCR terlihat jelas di admin |
| 5. RAG dan sesi | Retrieval, prompt, konteks lanjutan, referensi, abstain/konflik, streaming UI | Jawaban sesuai sumber, follow-up dipahami, sesi baru kosong |
| 6. Lifecycle dan hardening | Replace/delete, interrupted jobs, autentikasi, sanitasi, injection, failure handling | Dokumen lama tidak bocor melalui indeks; akses admin dan relay terkontrol |
| 7. Evaluasi dan penyerahan | Uji terarah, perbaikan, pengukuran latency, README/OpenAPI, demo/video | Bukti kelulusan kriteria, source siap diperiksa, langkah reproduksi dan keterbatasan tertulis |

Target pembagian waktu awal: 8 Oktober rancangan/fondasi; 9-10 Oktober relay dan ingestion; 11 Oktober OCR; 12 Oktober RAG/UI; 13 Oktober hardening/evaluasi; 14 Oktober verifikasi instalasi dan bahan penyerahan. Jadwal disesuaikan waktu mulai aktual, tanpa menambah fitur di luar scope untuk mengejar tampilan.

## 11. Kriteria penerimaan dan pengujian

| Area | Skenario | Hasil yang diharapkan |
| --- | --- | --- |
| Instalasi | Ikuti README dari lingkungan Windows bersih yang didukung | Aplikasi dapat dijalankan; dependensi Python/OCR dan kebutuhan internet jelas; penguji tidak mengisi API key OpenAI |
| KB kosong | Buka chat sebelum upload | Sapaan statis, informasi KB kosong, tidak mengarang jawaban |
| PDF teks | Upload dokumen Perpol | Teks terindeks, referensi halaman benar, sumber tidak tertukar |
| PDF scan | Upload pengumuman SBP | OCR/vision berjalan; teks kritis cocok dengan sumber dalam evaluasi; kegagalan/peringatan terlihat |
| Persistensi | Tutup aplikasi lalu jalankan kembali | PDF, teks, metadata, dan indeks tetap ada tanpa upload/embedding ulang |
| Edit metadata | Ubah judul dokumen | Judul referensi diperbarui secara konsisten tanpa embedding ulang isi yang sama |
| Replace | Ganti file, termasuk simulasi kegagalan | Versi baru aktif hanya setelah siap; versi lama tetap aktif jika penggantian gagal |
| Delete | Hapus dokumen yang pernah dipakai menjawab | Dokumen tidak dapat diretrieval kembali, termasuk melalui follow-up atau cache |
| Akurasi | Pertanyaan penilaian kinerja dan persyaratan SBP | Fakta dan dokumen sumber tepat; tidak mencampur dua substansi |
| Kelengkapan | Pertanyaan daftar persyaratan | Butir relevan terambil dan batas cakupan dijelaskan bila belum lengkap |
| Follow-up | Pertanyaan lengkap lalu "kalau SMA?" | Maksud diambil dari konteks dan jawaban memakai retrieval baru |
| Ambiguitas | Follow-up yang punya lebih dari satu tafsir | Meminta klarifikasi tanpa menebak fakta |
| Tidak tersedia | Pertanyaan di luar isi KB | Pernyataan sopan bahwa informasi belum ditemukan |
| Konflik | Fixture uji dua ketentuan berbeda | Perbedaan dan sumber dijelaskan, tanpa keputusan yang tidak didukung |
| Sesi | Refresh, tutup/buka chat, restart aplikasi, Percakapan baru | Riwayat/konteks tetap tersedia; hanya Percakapan baru menghapus sesi lama dan memulai kosong |
| Injection | Instruksi abaikan aturan, role palsu, serangan multi-turn dan dokumen | Tidak mengubah aturan, membocorkan rahasia, atau menjalankan tindakan admin |
| Admin | Endpoint admin dipanggil tanpa sesi valid | Ditolak backend; bukan hanya diarahkan oleh UI |
| Referensi | Sumber valid, ID sumber palsu, markdown link dari model | Hanya referensi valid berupa teks; tidak ada link/download PDF |
| Batas upload | PDF >100 MB, rusak, terkunci, ekstensi palsu | Ditolak dengan pesan yang jelas dan tidak merusak KB aktif |
| Kegagalan AI | Timeout, rate limit, internet putus, stream terputus | Pesan jelas, data persisten aman, jawaban parsial ditandai |
| Kecepatan | Pertanyaan sederhana, follow-up, pertanyaan kompleks | Latensi tiap tahap dicatat; tidak ada OCR ulang; streaming benar-benar muncul bertahap |
| Penyerahan | Periksa repository dan paket demo | Tidak ada key/password/token aktif atau data pribadi tak sengaja ikut dipublikasikan |

Siapkan set evaluasi faktual dari kedua dokumen setelah pembacaan isi lengkap. Catat pertanyaan, jawaban acuan yang diverifikasi, halaman, hasil retrieval, jawaban SIRA, dan hasil penilaian. Pisahkan fixture sintetis untuk konflik/injection dari knowledge base demo resmi.

Pengujian berfokus pada perilaku yang memengaruhi kebenaran, keamanan, persistensi, dan kelancaran demo; tidak perlu unit test yang sekadar menyalin implementasi atau menguji setiap detail styling.

## 12. Deliverables

- Source code di repository Git tanpa secrets dan tanpa data runtime.
- README berisi tujuan, stack, struktur proyek, arsitektur/workflow RAG, instalasi, setup admin, peluncuran aplikasi, konfigurasi relay, pengujian, dan troubleshooting.
- Dokumentasi API OpenAPI/Swagger sesuai panduan tugas.
- Catatan hasil evaluasi retrieval, jawaban, OCR, keamanan, dan latency.
- Panduan demo: mulai KB kosong, upload dua dokumen, tunjukkan status, tanya lintas sumber, follow-up, abstain, referensi, dan persistensi.
- Outline/naskah video dengan kamera peserta: perkenalan, stack, arsitektur, ingestion/parsing/chunking/embedding, vector database, pemilihan LLM, prompt, pengurangan halusinasi, sumber jawaban, keterbatasan, dan pengembangan lanjutan. Perekaman video dilakukan peserta.
- Keterbatasan terdokumentasi: ketergantungan internet/API, potensi kesalahan OCR/retrieval/LLM, serta belum ada klasifikasi akses dokumen. Review manual membantu koreksi tanpa menjamin ketepatan seluruh isi.

## 13. Hal yang diputuskan melalui eksperimen implementasi

Tidak ada keputusan produk yang menghalangi penyusunan rencana atau tahap fondasi. Hal berikut diselesaikan melalui uji teknis, bukan menambah diskusi fitur:

- Versi Python/library yang paling stabil untuk lingkungan Windows penguji.
- Kualitas Tesseract pada scan aktual serta kebutuhan preprocessing/bantuan vision.
- Ukuran chunk, overlap, jumlah kandidat retrieval, serta anggaran konteks.
- Batas rate/token/biaya akses uji berdasarkan anggaran peserta sebelum relay diaktifkan untuk penguji.
- Kesesuaian ukuran payload vision dan streaming dengan batas Worker yang digunakan.
- Angka latency aktual dan penyesuaian yang diperlukan.

## 14. Referensi teknis

- FastAPI dan dokumentasi API: https://fastapi.tiangolo.com/tutorial/first-steps/
- Vite build: https://vite.dev/guide/build
- Chroma PersistentClient: https://docs.trychroma.com/reference/python/client
- Tesseract dan kualitas OCR: https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html
- GPT-4o mini: https://developers.openai.com/api/docs/models/gpt-4o-mini
- GPT-4.1 mini, khusus opsi admin Baca dengan AI untuk scan gagal (disetujui 8 Oktober 2026): https://developers.openai.com/api/docs/models/gpt-4.1-mini
- Model embedding: https://developers.openai.com/api/docs/models/text-embedding-3-small
- OpenAI images/vision: https://developers.openai.com/api/docs/guides/images-vision
- Cloudflare Secrets: https://developers.cloudflare.com/workers/configuration/secrets/
- Cloudflare streaming: https://developers.cloudflare.com/workers/runtime-apis/streams/
- Cloudflare limits: https://developers.cloudflare.com/workers/platform/limits/
- OWASP prompt injection: https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html

Referensi ini merupakan pedoman teknis; batas layanan dan kompatibilitas diverifikasi kembali saat implementasi.

# Penerapan OCR nyata SBP, 8 Oktober 2026

Pengguna meminta pipeline diterapkan pada dokumen SBP yang tersimpan, setelah membedakan hasil lama dari uji pembanding. Halaman 1–4 yang sudah lolos GPT-4.1 mini dipakai ulang. Halaman 5–12 diproses dengan OCR lokal, mini pertama, mini kedua bila perlu, lalu Sol pada crop yang belum konsisten. Respons setiap tahap tersimpan di SQLite yang sama dengan aplikasi, tanpa fixture pengganti.

## Hasil

| Model | Request berhasil | Token input / output | Estimasi biaya |
| --- | --- | --- | --- |
| GPT-4.1 mini | 86 | 126.771 / 11.914 | US$0,0697708 |
| GPT-5.6 Sol | 5 | 5.858 / 1.048 | US$0,0443920 |
| Total | 91 | 132.629 / 12.962 | **US$0,1141628** |

Sekitar **Rp1.941** dengan asumsi ilustrasi Rp17.000/US$, bukan kurs kartu terverifikasi. Ini tambahan run ini, di luar uji sebelumnya; tidak ada retry HTTP otomatis. Waktu request berurutan sekitar 268,7 detik, di luar OCR lokal, render, dan deployment. Cached input seluruh request 0; output mencakup reasoning yang ditagihkan. Tarif acuan: [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini), [GPT-5.6 Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol). Pajak/biaya lain tidak masuk.

**10 halaman lolos otomatis: 1–9 dan 11. Dua halaman wajib review: 10 dan 12**, seluruhnya belum dikonfirmasi manusia. SBP belum aktif, tidak ada embedding/index baru atau perubahan KB aktif Perpol.

Sol terpicu alami lima kali: halaman 8 sekali, halaman 10 dua kali, halaman 12 dua kali. Pada halaman 8 bagian 5, mini pertama melewatkan baris terakhir, mini kedua menyertakannya, dan Sol mempertahankan baris itu. Crop asli diperiksa secara visual dan baris memang terlihat. Ini membuktikan eskalasi nyata memperbaiki satu kasus, bukan akurasi umum.

Halaman 10 bagian 5 memuat cap/tanda tangan yang menutupi teks; Sol memberi `uncertain=true`. Bagian 6 tetap tidak cocok pada tanda/angka yang sangat pendek. Halaman 12 bagian 5 hampir kosong dengan coretan pendek: salah satu bacaan mini mengarang transkripsi panjang dokumen lain meskipun `uncertain=false`; Sol menghasilkan teks kosong, sehingga hasil tidak terverifikasi dan ditahan. Bagian 6 tidak memperoleh eskalasi ketiga karena batas dua Sol per halaman. Daftar wajib review tidak menyatakan bahwa semua isi halaman tersebut salah.

Draft halaman 1 yang sebelumnya tersimpan oleh uji UI ternyata identik persis dengan teks AI yang telah lolos. Teks/revisi tetap dipertahankan; hanya kewajiban konfirmasi tambahan dilepas. Tidak ada edit pengguna yang berbeda ditimpa atau status konfirmasi manusia yang dipalsukan. Backup SQLite sebelum pemrosesan, ledger biaya, respons API, serta gambar pemeriksaan berada di `tmp/sbp-regional-real-v3/`, diabaikan Git.

## Batas biaya dan deployment

Run pertama tertahan `relay_budget` sebelum OpenAI meskipun versi sementara menunjukkan 12 juta unit. Tidak ada tambahan biaya OpenAI pada percobaan tersebut. Percobaan penerapan ulang dengan pembatas lokal saja ditolak pemeriksaan persetujuan otomatis. Solusi yang dijalankan menambahkan batas biaya di server, bukan menghindari kuota.

Durable Object tetap memakai counter unit/request yang sama, ditambah anggaran bersama **US$0,50** (`RUN_BUDGET_ID=sbp-real-20261008-50c`, `RUN_BUDGET_MICRO_USD=500000`). Reservasi biaya atomik mendahului OpenAI; usage valid menyelesaikan biaya nyata, sedangkan gagal/usage tidak tersedia mempertahankan reservasi konservatif. Batas unit terkini diteruskan dari handler Worker agar tidak bergantung pada nilai konstruktor lama. Perubahan tidak mereset counter, mengganti ID budget, memperpanjang expiry, atau mengganti secrets. Lihat [relay-setup.md](relay-setup.md).

Selesai ingestion, batas unit kembali **2 juta** dan anggaran server ID yang sama tetap ada. Versi aktif: **ff6e5a0e-1d8f-4d08-bdae-8a4663c81c69**. Upaya membuka 12 juta unit untuk indeks/chat berikutnya ditolak pemeriksaan persetujuan otomatis karena dianggap pemakaian lanjutan di luar izin OCR. Deployment itu tidak dijalankan. Pemilik perlu mengizinkan kuota lanjutan sebelum embedding hasil review atau chat dapat memakai sisa anggaran; hasil OCR tidak perlu dibaca ulang.

## Verifikasi aplikasi

- 35 tes backend lulus, 1 live opt-in dilewati; satu peringatan deprecation TestClient/httpx. Run pertama gagal membuat direktori fixture temp pada sandbox; rerun pada direktori workspace lulus. Setelah metadata metode crop ditambahkan, tes integrasi review terkait diulang dan lulus. Ruff lulus.
- 7 tes policy/biaya dan 9 tes runtime Worker lulus dengan key palsu. Type check/dry-run lulus. Tes mencakup anggaran bersama sebelum upstream, settlement, reservasi serentak, override klien, anggaran invalid, dan kegagalan upstream yang menahan biaya.
- Build frontend lulus. Aplikasi direstart setelah ingestion selesai. Browser nyata desktop 1440×1100 dan mobile 390×844 menampilkan hanya nomor halaman 10 dan 12, langsung membuka 10, preview crop berhasil, dan ada keterangan bagian yang sudah diperiksa Sol tetapi belum lolos. Mode seluruh halaman menampilkan 12 nomor. Tombol indeks tetap ditahan sebelum konfirmasi. Tanpa error JavaScript/overflow horizontal atau panggilan AI tambahan.
- Health tetap satu dokumen aktif (Perpol), revision 1. Tidak ada konfirmasi manual, aktivasi SBP, atau penilaian akurasi seluruh teks oleh manusia pada uji ini.

## Setelah review manusia: indeks berhasil

Pengguna kemudian mengonfirmasi halaman 10 dan 12 melalui admin dan menjalankan indexing. Review tersimpan, tetapi embedding ditolak karena kuota unit relay sudah kembali 2 juta. Pada tahap ini mode versi `manual`, seluruh 12 teks telah diterima, tanpa chunk baru; error tersebut adalah batas layanan, bukan penolakan hasil review.

Atas permintaan pengguna untuk menyelesaikan kegagalan itu, kuota sementara **9 juta unit** digunakan hanya selama pembuatan indeks. Anggaran server US$0,50 memakai ID yang sama, tanpa reset. Skrip menolak seluruh operasi selain embedding, maksimum empat request dan tambahan US$0,01, serta selalu memulihkan versi relay sebelumnya. Tidak ada vision atau chat.

Hasil: **3 request embedding**, 10.558 token input, **US$0,00021116** (sekitar Rp4 dengan asumsi Rp17.000/US$). Dua batch masing-masing 12 chunk dan satu batch 1 chunk selesai. SBP kini **aktif/ready**, 12 halaman dan **25 chunk/vektor persisten** yang mencakup PDF halaman 1–12. Aplikasi direstart, browser admin menunjukkan siap digunakan, health dua dokumen aktif/revision 2, tanpa error JavaScript. Pemeriksaan Chroma dari proses terpisah memastikan semua vektor tersimpan. Tidak ada OCR ulang atau perubahan teks/konfirmasi tambahan oleh agen.

Total OCR nyata di laporan ini dan indexing tersebut sekitar **US$0,11437396**. Ini tidak mencakup uji pembanding sebelumnya atau pemakaian pengguna yang tidak tercatat dalam ledger skrip.

Relay sudah dipulihkan ke versi **ff6e5a0e-1d8f-4d08-bdae-8a4663c81c69**, batas unit 2 juta dan anggaran server US$0,50 yang sama. Izin untuk mempertahankan kuota lebih tinggi bagi chat demo belum diberikan; jangan menyatakan panggilan chat sudah kembali tersedia hanya karena dokumen siap. Bukti lokal berada di `tmp/sbp-index-confirmed/`, diabaikan Git.

## Pembaruan: pemilik meminta batas total dihapus

Setelah chat ikut tertahan, pemilik secara eksplisit meminta “gak usah dibatas-batasin”. Pada 8 Oktober 2026, versi **b0ada031-35af-436e-929c-c7ccdcd0105f** dideploy dengan `TOTAL_QUOTA_ENABLED=false`. Seluruh endpoint AI tidak lagi memeriksa batas kumulatif request/unit maupun anggaran uji aplikasi. Nilai/ID anggaran lama tetap tersimpan untuk riwayat dan tidak direset. Mode kuota uji masih tersedia jika pemilik mengaktifkannya kembali. Autentikasi, validasi operasi/model/payload, proteksi 30 request/menit, serta expiry 16 Oktober 2026 pukul 03:42:55 UTC tetap berlaku. Pemakaian kini mengikuti saldo/batas penyedia dan ditagihkan sesuai penggunaan akun.

Verifikasi: type check, 7 tes policy/biaya, 10 runtime Worker, dan build dry-run lulus. Percobaan runtime awal pada sandbox ditolak akses SQLite Windows; rerun dengan izin runtime lokal lulus. Tes baru memastikan semua endpoint melewati nilai total request/unit/biaya yang sangat kecil saat mode dimatikan, tetapi request keenam tetap ditolak oleh rate limit lima/menit pada fixture, dan override payload klien tetap ditolak.

Chat nyata melalui browser berhasil menjawab pertanyaan tujuan Sistem Manajemen Kinerja Polri menggunakan GPT-4o mini dengan referensi Perpol Nomor 1 Tahun 2025 halaman PDF 1, tanpa pesan kuota atau error JavaScript. Percobaan pertama membaca body SSE melalui API Playwright gagal pada sisi alat pemeriksa; verifikasi berikutnya membaca teks/referensi langsung dari UI dan berhasil. Tidak ada OCR, indexing ulang, atau perubahan dokumen. Screenshot/hasil berada di `tmp/relay-no-total/` dan diabaikan Git. Status pemakaian lanjutan yang disebut masih menunggu izin pada bagian historis di atas sudah digantikan oleh keputusan ini.

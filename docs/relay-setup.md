# Relay pengujian Cloudflare

Petunjuk ini untuk peserta/pemilik akun. Penguji cukup memasang aplikasi lokal dan menerima akses relay. Model yang ditetapkan server: GPT-6 Luna untuk jawaban, GPT-6 Luna untuk bantuan OCR, GPT-5.6 Sol untuk fallback crop meragukan, dan text-embedding-3-small untuk embedding. Klien tidak dapat menentukan model arbitrer. Atas permintaan pemilik pada 8 Oktober 2026, batas kumulatif request, unit, dan biaya aplikasi dinonaktifkan; autentikasi, proteksi spam per menit, serta masa berlaku tetap aktif.

## Setup dengan skrip

Untuk **instalasi penguji**, gunakan [alur koneksi otomatis](automatic-installation.md). Penguji tidak menjalankan skrip konfigurasi pemilik di bagian ini. Demo publik aktif setelah izin pemilik; konfigurasi AI terisi melalui `setup.ps1`/`start.ps1` tanpa memasukkan key/token. Perbarui atau cabut akses demo memakai `scripts/deploy-automatic-relay.ps1`, yang mempertahankan variabel deployment aktif. Skrip konfigurasi awal di bawah dapat menonaktifkan kembali akses demo sesuai konfigurasi distribusi default.

Pastikan Node.js tersedia, lalu login sekali:

```powershell
cd worker
npm ci
npx wrangler login
cd ..
.\scripts\configure-relay.ps1
```

Skrip meminta API key melalui `Read-Host -AsSecureString`, menerbitkan Worker dalam kondisi nonaktif, menyimpan `OPENAI_API_KEY` dan `RELAY_TOKEN_HASH` melalui Cloudflare Secrets, lalu mengaktifkan dan menerbitkan kembali Worker. Key diteruskan lewat stdin, bukan argumen command line. Jangan mengaktifkan transcript/debug terminal saat memasukkan rahasia.

Tempel URL `https://sira-relay.<subdomain>.workers.dev` dari output Wrangler saat diminta. Skrip menyimpan URL dan token akses terbatas pada `.env` lokal; API key OpenAI tidak ditulis ke `.env`. Token lokal berada juga di `data/relay-token.txt`, keduanya diabaikan Git. Masa akses default 8 hari; gunakan `-Days 3` untuk mengubahnya. Restart backend setelah konfigurasi berubah, kemudian login admin dan pilih **Uji koneksi AI**.

Jika deployment awal gagal, skrip berhenti sebelum mengaktifkan akses. Jika pemasangan secret atau deployment akhir gagal, periksa status di Cloudflare Dashboard sebelum mencoba ulang. Skrip memodifikasi variabel aktivasi/tanggal pada `worker/wrangler.toml`; konfigurasi distribusi sebaiknya memakai `RELAY_ENABLED = "false"` secara default.

## Batas penggunaan

| Variabel | Default | Arti |
| --- | --- | --- |
| `RELAY_ENABLED` | `false` sebelum setup | Sakelar akses seluruh relay |
| `RELAY_EXPIRES_AT` | Diisi setup | UTC, akses ditolak setelah waktu ini |
| `TOTAL_QUOTA_ENABLED` | `false` | Jika `false`, batas total request/unit dan anggaran `RUN_BUDGET_*` tidak diberlakukan. Jika tidak diset, perilaku lama tetap aktif. Hanya konfigurasi server yang dapat mengubahnya. |
| `MAX_REQUESTS` | 1000 | Total request yang direservasi sejak penghitung dibuat |
| `MAX_TOKEN_UNITS` | 2000000 | Total unit reservasi konservatif sejak penghitung dibuat |
| `REQUESTS_PER_MINUTE` | 30 | Batas seluruh pemegang token per menit |
| `RUN_BUDGET_ID` | Tidak diset | ID anggaran uji yang tetap selama satu rangkaian pemakaian |
| `RUN_BUDGET_MICRO_USD` | Tidak diset | Batas biaya berdasarkan tarif model, dalam mikro-USD; 500000 = US$0,50 |

Dengan `TOTAL_QUOTA_ENABLED = "false"`, nilai `MAX_REQUESTS`, `MAX_TOKEN_UNITS`, dan `RUN_BUDGET_*` tidak memblokir chat, OCR, atau embedding. Penghitung historis tidak dihapus. Pemakaian tetap ditagihkan oleh OpenAI sesuai akun pemilik; batas/saldo dari penyedia tetap berlaku. Proteksi 30 request/menit membatasi lonjakan sesaat dan tidak menghabiskan jatah kumulatif.

Bagian anggaran berikut menjelaskan mode uji opsional saat `TOTAL_QUOTA_ENABLED` diaktifkan kembali. Unit reservasi bukan hitungan token tagihan atau batas dolar yang presisi. Teks menggunakan ukuran byte UTF-8 ditambah reservasi output; vision GPT-6 Luna menggunakan 60000 unit per request, fallback potongan GPT-5.6 Sol menggunakan 200000. Request gagal setelah reservasi tetap mengurangi jatah. Penghitung disimpan pada Durable Object dan tidak direset hanya dengan redeploy atau mengganti tanggal/token.

Biaya Cloudflare/OpenAI mengikuti akun pemilik. Vision untuk scan dapat menghabiskan kuota lebih cepat daripada chat sederhana. Nilai batas tersedia untuk diubah sebelum pemberian akses penguji.

## Anggaran biaya uji di server

Jika mode kuota total aktif dan kedua variabel `RUN_BUDGET_*` diset, seluruh endpoint memakai anggaran bersama yang ditegakkan oleh Durable Object sebelum menghubungi OpenAI. Satu variabel saja atau nilai tidak valid membuat akses gagal tertutup. ID dan batas hanya berasal dari konfigurasi Worker, bukan payload klien. Anggaran unit/request/rate tetap diperiksa pada counter lama; menambahkan anggaran biaya tidak mereset atau menggantikan counter tersebut.

Setiap permintaan memesan biaya konservatif terlebih dahulu. Respons vision/embedding yang lengkap dan memiliki usage valid mengembalikan selisih reservasi, memakai harga model di `src/cost.ts` (diperiksa 8 Oktober 2026). Completion token sudah mencakup reasoning; cached input dihitung sesuai tarifnya. Streaming chat tetap memesan estimasi konservatif penuh. Respons gagal, usage tidak tersedia, atau pemutusan koneksi menahan reservasi, sehingga retry tidak dapat melewati batas lewat kegagalan. ID yang sama mempertahankan pemakaian saat redeploy; jangan membuat ID baru untuk menghindari anggaran yang telah habis.

Kode `relay_cost` menandakan sisa anggaran tidak cukup untuk reservasi satu permintaan, meski masih ada unit relay. Reservasi vision mini US$0,015 dan Sol US$0,15 sengaja lebih besar daripada biaya sampel; karena itu proses dapat berhenti sebelum total biaya aktual mencapai batas. Perhitungan ini memakai asumsi batas input gambar/model tetap serta tarif saat diperiksa, bukan janji tagihan kartu yang identik; pajak, perubahan harga, kurs, dan biaya Cloudflare tidak masuk. Tinjau harga sebelum mengubah model atau batas gambar/output.

Batas unit terkini diteruskan dari handler Worker pada setiap reservasi internal agar perubahan binding tidak bergantung pada nilai lama yang tersimpan di konstruktor Durable Object. Endpoint reservasi/settlement hanya dapat diakses lewat binding internal; tidak ada route publik untuk mengatur biaya, mengganti batas, menghapus pemakaian, atau membaca secrets.

## Pencabutan dan rotasi

Untuk mencabut seluruh akses, set `RELAY_ENABLED = "false"` pada `worker/wrangler.toml`, lalu jalankan `npm run deploy` dalam folder Worker. Masa berlaku otomatis juga menolak akses yang kedaluwarsa.

Untuk mengganti token, buat token baru lokal dengan skrip generator (menolak overwrite token lama), masukkan hash SHA-256 token baru sebagai secret `RELAY_TOKEN_HASH`, dan perbarui `.env` aplikasi yang berwenang. Jangan menaruh token mentah pada source, URL, screenshot, atau log. Token lama tidak berlaku setelah secret hash diganti. Rotasi API key utama dilakukan melalui Cloudflare Secrets dan OpenAI, terpisah dari token penguji.

## Batas kepercayaan

Relay hanya menerima `POST /embeddings`, `/answer`, `/vision` (GPT-6 Luna), dan `/vision-fragment` (GPT-5.6 Sol, satu JPEG maksimal payload 2 MB), dengan skema terbatas. Model, endpoint OpenAI, instruksi sistem, dan anggaran output ditetapkan di Worker. Tidak ada arbitrary URL proxy atau model dari klien. Tidak ada CORS browser publik; backend lokal yang menghubungi relay. Pembatasan luas crop dan jumlah eskalasi per halaman dilakukan backend.

Pemilik PC dapat mengekstrak token relay lokal. Perlindungan akses penguji berupa masa berlaku, batas operasi, rate limit, dan pencabutan. Token tersebut tidak memberikan akses Cloudflare Dashboard atau API key OpenAI. Tanpa kuota total aplikasi, token yang masih berlaku dapat terus memicu biaya; ini adalah pilihan pemilik untuk prototype ini.

Data pertanyaan, potongan dokumen, dan gambar halaman yang memerlukan vision dikirim melalui Cloudflare ke OpenAI. PDF asli dan indeks tetap berada di PC. Jangan memasukkan dokumen yang tidak diizinkan untuk pemrosesan tersebut.

# Relay pengujian Cloudflare

Petunjuk ini untuk peserta/pemilik akun. Penguji cukup memasang aplikasi lokal dan menerima akses relay terbatas. Model yang ditetapkan server: GPT-4o mini untuk jawaban/vision otomatis, GPT-4.1 mini khusus tombol admin **Baca dengan AI**, dan text-embedding-3-small untuk embedding. Pilihan OCR berupa flag boolean tervalidasi; klien tidak dapat menentukan model arbitrer. Kuota dan masa berlaku relay tetap sama.

## Setup dengan skrip

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
| `MAX_REQUESTS` | 1000 | Total request yang direservasi sejak penghitung dibuat |
| `MAX_TOKEN_UNITS` | 2000000 | Total unit reservasi konservatif sejak penghitung dibuat |
| `REQUESTS_PER_MINUTE` | 30 | Batas seluruh pemegang token per menit |

Unit reservasi bukan hitungan token tagihan atau batas dolar yang presisi. Teks menggunakan ukuran byte UTF-8 ditambah reservasi output; vision GPT-4.1 mini menggunakan 60000 unit per request, fallback potongan GPT-5.6 Sol menggunakan 200000. Request gagal setelah reservasi tetap mengurangi jatah. Penghitung disimpan pada Durable Object dan tidak direset hanya dengan redeploy atau mengganti tanggal/token. Periksa pula penggunaan pada akun OpenAI; batas proyek harus disesuaikan oleh pemilik akun.

Biaya Cloudflare/OpenAI mengikuti akun pemilik. Vision untuk scan dapat menghabiskan kuota lebih cepat daripada chat sederhana. Nilai batas tersedia untuk diubah sebelum pemberian akses penguji.

## Pencabutan dan rotasi

Untuk mencabut seluruh akses, set `RELAY_ENABLED = "false"` pada `worker/wrangler.toml`, lalu jalankan `npm run deploy` dalam folder Worker. Masa berlaku otomatis juga menolak akses yang kedaluwarsa.

Untuk mengganti token, buat token baru lokal dengan skrip generator (menolak overwrite token lama), masukkan hash SHA-256 token baru sebagai secret `RELAY_TOKEN_HASH`, dan perbarui `.env` aplikasi yang berwenang. Jangan menaruh token mentah pada source, URL, screenshot, atau log. Token lama tidak berlaku setelah secret hash diganti. Rotasi API key utama dilakukan melalui Cloudflare Secrets dan OpenAI, terpisah dari token penguji.

## Batas kepercayaan

Relay hanya menerima `POST /embeddings`, `/answer`, `/vision` (GPT-4.1 mini), dan `/vision-fragment` (GPT-5.6 Sol, satu JPEG maksimal payload 2 MB), dengan skema terbatas. Model, endpoint OpenAI, instruksi sistem, dan anggaran output ditetapkan di Worker. Tidak ada arbitrary URL proxy atau model dari klien. Tidak ada CORS browser publik; backend lokal yang menghubungi relay. Pembatasan luas crop dan jumlah eskalasi per halaman dilakukan backend; token relay tetap dibatasi kuota karena pemilik PC dapat mengekstraknya.

Pemilik PC dapat mengekstrak token relay lokal. Karena itu perlindungan utama akses penguji adalah masa berlaku, kuota persisten, batas operasi, rate limit, dan pencabutan. Token tersebut tidak memberikan akses Cloudflare Dashboard atau API key OpenAI.

Data pertanyaan, potongan dokumen, dan gambar halaman yang memerlukan vision dikirim melalui Cloudflare ke OpenAI. PDF asli dan indeks tetap berada di PC. Jangan memasukkan dokumen yang tidak diizinkan untuk pemrosesan tersebut.

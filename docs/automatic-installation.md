# Koneksi otomatis instalasi penguji

> **Model aktif saat ini (10 Oktober 2026):** jawaban chat **GPT-6 Luna**; OCR AI **GPT-6 Luna** dengan fallback **GPT-5.6 Sol**; embedding **text-embedding-3-small**. Hasil verifikasi 9 Oktober di bawah memakai model jawaban saat itu (GPT-4o mini).

Tambahan 9 Oktober 2026. Pengguna memberikan persetujuan eksplisit untuk demo publik selama masa pengujian. Pemrosesan OCR, retrieval, prompt/model jawaban, akun admin, dan data knowledge base tidak diubah.

## Alur penguji

1. Pasang Python 3.12 dan Node.js 24 sesuai README, unduh repository, dan buka PowerShell pada folder proyek.
2. Jalankan `setup.ps1` dengan path Python yang sesuai. Setup memasang dependensi dan meminta akun admin lokal. Password dipilih penguji, bukan password pemilik.
3. Setup menjalankan `python -m backend.setup_relay`. Endpoint dari `config/relay.json` menyediakan URL/token demo dan masa berlaku. Keduanya disimpan atomik pada `.env`, tanpa ditampilkan di terminal. Tidak ada API key OpenAI yang dikirim.
4. Pasang OCR menggunakan `scripts/setup-ocr.ps1`, lalu jalankan `start.ps1`. Launcher juga mengisi konfigurasi AI jika belum tersedia; konfigurasi lengkap yang sudah ada tetap dipertahankan.
5. Login `/admin`, pilih **Uji koneksi AI**, lalu upload dokumen. Pemeriksaan koneksi memakai embedding OpenAI kecil berbayar; pengambilan konfigurasi sendiri tidak memanggil OpenAI.

Setup tidak menyatakan selesai jika konfigurasi otomatis gagal. Tidak ada fallback jawaban AI tiruan. URL/token custom yang baru terisi sebagian tidak ditimpa; lengkapi konfigurasi tersebut terlebih dahulu. Redirect, perubahan origin relay, respons rusak, credential berbentuk key OpenAI, serta expiry tidak valid/berakhir ditolak sebelum `.env` diubah.

## Batas akses publik

`GET /installation` adalah endpoint demo publik, bukan mekanisme verifikasi identitas penguji. Semua orang yang mengetahui endpoint dapat memperoleh token demo selama pemilik mengaktifkannya. Token tersebut dapat dibaca pemilik laptop; menyimpannya sebagai Cloudflare Secret tidak menjadikannya rahasia setelah dibagikan melalui endpoint ini.

Token demo berbeda dari token privat yang sudah dipakai pemilik. API key OpenAI tetap hanya berada di Cloudflare Secrets. Endpoint tidak mengembalikan key, hash/token privat, isi dokumen, atau akun admin. Tidak ada akses ke Cloudflare Dashboard atau fungsi admin melalui token demo.

Demo memakai autentikasi token, operasi dan model fixed, validasi payload, masa berlaku, serta counter/proteksi per menit yang sama dengan relay sebelumnya. Tidak ada bypass/clear counter. Batas kumulatif tetap nonaktif sesuai keputusan pemilik sebelumnya. Pemakaian pihak lain dapat menyebabkan biaya OpenAI dan memakai kapasitas proteksi per menit bersama.

Masa akses saat ini: **30 Oktober 2026 pukul 23.59 WIB**, tepat `2026-10-30T16:59:59Z`. Pemilik meminta perpanjangan pada 9 Oktober 2026 agar penguji tetap dapat mencoba setelah wawancara. Token instalasi yang sudah terpasang tetap sama; tidak perlu setup ulang. Data lokal tidak dihapus ketika akses AI berakhir.

## Aktivasi dan pencabutan oleh pemilik

Skrip berikut hanya untuk pemilik akun Cloudflare yang sudah login CLI dan memiliki relay aktif dengan secret OpenAI:

```powershell
.\scripts\deploy-automatic-relay.ps1
```

Skrip membaca konfigurasi deployment aktif, mempertahankan seluruh variabel non-rahasia termasuk masa berlaku/kuota, menyiapkan token demo terpisah di `data/installation-token.txt`, memasukkannya ke Cloudflare Secret `INSTALLATION_TOKEN`, lalu deploy dengan `INSTALLATION_ACCESS_ENABLED=true`. Key OpenAI dan token privat tidak dibaca atau diubah. Tidak mengubah `.env` pemilik. Konfigurasi release sementara `worker/.wrangler-auto-install.toml` dan file token diabaikan Git.

Untuk mencabut jalur demo dan semua token demo yang sudah terpasang, sambil mempertahankan token privat:

```powershell
.\scripts\deploy-automatic-relay.ps1 -Disable
```

Mematikan seluruh relay dapat dilakukan melalui `RELAY_ENABLED=false` sesuai panduan relay. Jika pemilik memang mengizinkan perpanjangan, `-Days 3` menetapkan expiry baru tiga hari; tanpa parameter ini masa berlaku lama dipertahankan. Instalasi custom/privat tetap menggunakan cara konfigurasi pada `docs/relay-setup.md`.

`worker/wrangler.toml` yang dilacak Git tetap nonaktif secara default. Deploy langsung konfigurasi tersebut akan menonaktifkan akses; gunakan skrip pemilik di atas untuk memperbarui kode tanpa kehilangan pengaturan aktif.

## Hasil verifikasi 9 Oktober 2026

- Deployment nyata: versi `c95c9dad-dddb-4909-bf51-86b9a0728b66`, relay aktif dan instalasi publik aktif, expiry lama dipertahankan. Token demo terpisah dipasang sebagai secret baru; variabel deployment yang sudah ada dipertahankan, termasuk kuota kumulatif nonaktif, proteksi 30 request/menit, dan ID anggaran historis.
- Backend: 85 passed, 1 live opt-in skipped; 12 tes baru memeriksa setup otomatis, konfigurasi custom/environment, penyimpanan atomik, token tidak ditampilkan, cross-origin, expiry, redirect, dan kegagalan layanan. Ruff lulus.
- Relay: 8 policy/cost dan 13 runtime Miniflare passed, TypeScript dan bundel dry-run lulus. Tes memeriksa demo tidak membocorkan key/token privat, pencabutan, expiry, auth lama, model arbitrer, serta proteksi per menit yang dibagi bersama.
- Parser PowerShell setup/start/deploy lulus. Pengambilan konfigurasi nyata dari `.env` kosong berhasil dan memperoleh token berbeda dari token pemilik, tanpa key OpenAI.
- Integrasi nyata menggunakan database baru terpisah: KB mulai kosong, login admin baru berhasil, satu PDF teks sintetis selesai diindeks menjadi satu chunk, query embedding dan satu jawaban GPT-4o mini selesai dengan kode fixture yang benar dan referensi halaman 1. Riwayat bisa diambil kembali. Tidak ada pemanggilan vision atau perubahan dua dokumen utama.
- Sebelum deployment, dua request kecil melalui token privat pemilik juga berhasil: embedding 1536 dimensi dan stream OpenAI dengan model `gpt-4o-mini-2024-07-18`. Sesudah deployment, fixture menggunakan token demo yang diperoleh otomatis. Total uji OpenAI nyata pada pengerjaan ini: lima request kecil (tiga embedding dan dua jawaban), tanpa OCR berbayar atau retry jawaban.
- Scan kandidat source/dokumentasi tidak menemukan token privat atau token demo aktual; file token/config release tetap diabaikan Git. Pengujian tidak mengklaim bahwa token demo publik merupakan rahasia.

Bukti lokal berada di `tmp/automatic-install-live/` dan skrip `tmp/automatic-install-live-check.py`, diabaikan Git. Uji memakai runtime/dependensi yang sudah ada di PC pengembang; ini membuktikan bootstrap dan integrasi dari konfigurasi/data kosong, bukan instalasi seluruh dependensi pada Windows bersih atau keberhasilan pada setiap laptop.

## Perpanjangan akses sampai 30 Oktober 2026

Atas permintaan pemilik, expiry diperpanjang dari 16 Oktober menjadi **30 Oktober 2026 pukul 23.59 WIB** (`2026-10-30T16:59:59Z`). Deployment aktif hasil perubahan: `22e13371-660a-40a7-bbb7-b6a186a32c17`. Endpoint instalasi sudah mengembalikan tanggal baru. Token demo yang diperoleh sebelum perubahan tetap identik; seluruh binding selain expiry, termasuk secrets, counter dan proteksi per menit, dipertahankan. Tidak ada request OpenAI pada deployment/verifikasi endpoint. Instalasi yang sudah memiliki URL/token tidak perlu setup ulang atau restart untuk memakai masa akses baru.

Verifikasi tambahan: konfigurasi instalasi kosong berhasil mengambil masa akses baru; menjalankan bootstrap kedua kali mempertahankan konfigurasi yang ada. Token privat dan demo diterima pada relay dengan payload embedding sengaja tidak valid (400 sebelum OpenAI). Dua belas tes bootstrap lulus. Tidak ada request AI berbayar, OCR, atau indexing ulang. Bukti lokal: `tmp/expiry-extension-result.json` dan snapshot binding sebelum/sesudah, diabaikan Git.

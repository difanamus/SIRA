# OCR bertahap dan review selektif

Keputusan pengguna, 8 Oktober 2026: OCR lokal → GPT-4.1 mini → GPT-5.6 Sol, dengan Sol hanya membaca bagian yang masih meragukan. Luna tidak dipakai. Model chat tetap GPT-4o mini.

## Alur yang diterapkan

1. PDF teks diekstrak langsung. Scan dibagi menjadi enam potongan berurutan tanpa overlap; tiap potongan maksimal 25% tinggi halaman. Batas berada di sela baris atau garis penuh tabel, sehingga sel jadwal gabungan tidak dipisahkan. Jika batas aman tidak ditemukan, sistem meminta review, tanpa mengirim seluruh halaman ke Sol.
2. OCR lokal berjalan pada setiap potongan nonkosong. Bantuan mini diperlukan bila confidence di bawah 95, teks sangat sedikit, atau terdapat angka/negasi/ketentuan penting. Confidence bukan probabilitas akurasi yang terkalibrasi. Angka diperiksa meski confidence tinggi.
3. GPT-4.1 mini membaca gambar yang diperjelas. Jika hasil terbaca dan cocok dengan OCR lokal, diterima. Jika berbeda atau ragu, mini membaca gambar asli tanpa diberi transkripsi pertama. Pemeriksaan membandingkan angka/negasi/semester beserta posisi token dan operator rumus, bukan hanya jumlah angka.
4. Jika dua pembacaan mini masih berbeda/ragu, Sol membaca hanya potongan itu dari gambar asli. Model dan instruksi ditetapkan Worker, reasoning low, maksimal 4.000 token output termasuk reasoning, tanpa tools. Sol tidak menerima transkripsi sebelumnya. Hasil harus terbaca, tidak ragu, dan sesuai salah satu pembacaan mini. Jika tetap berbeda, diperlukan review admin.
5. Maksimal dua potongan per halaman dikirim ke Sol. Ini mencegah seluruh halaman yang buruk dikirim sepotong demi sepotong ke model mahal. Potongan lainnya tetap dapat diproses mini; jika masih ragu masuk review.
6. Hasil lokal, mini pertama/kedua, Sol, lokasi crop, dan status disimpan per versi/halaman/potongan dalam SQLite. Retry setelah gangguan memakai respons yang sudah tersimpan. Kegagalan autentikasi, jaringan, dan kuota tidak memicu Sol. Respons transkripsi rusak/terpotong diperlakukan sebagai hasil ragu, bukan kegagalan jaringan.
7. Halaman yang belum lolos tidak masuk indeks. Pemrosesan dapat melanjutkan halaman lainnya, lalu otomatis membuka status menunggu review. Admin memilih crop terkait; teks gabungan tetap tersedia untuk koreksi. Halaman lolos otomatis tidak perlu dikonfirmasi ulang. Edit manual tetap membutuhkan konfirmasi dan dilindungi revision agar tab lama tidak menimpa perubahan.

Tombol **Baca dengan AI** memaksa pemeriksaan mini pada semua potongan nonkosong yang belum lolos pemeriksaan AI. OCR lokal tetap tahap pertama. Hasil GPT-4.1 mini versi sebelumnya yang sudah diterima dipertahankan. Draft manual tersimpan tidak ditimpa oleh pembacaan ulang. Review lokal tidak memanggil API vision; indeks akhir tetap menggunakan embedding.

## Biaya dan kuota

Tarif resmi saat diperiksa: GPT-4.1 mini input US$0,40/output US$1,60 per juta token; GPT-5.6 Sol input US$4/output US$20. Karena Sol lebih mahal, hanya crop bermasalah yang dikirim. Respons API, reasoning, resolusi, retry, dan panjang teks memengaruhi biaya. Tidak ada jaminan akurasi 100% ataupun batas biaya dolar dari mekanisme reservasi relay.

Permintaan mini menggunakan 60.000 unit reservasi internal, Sol 200.000. Kuota total tetap menggunakan Durable Object yang sama; tidak direset atau dilewati dengan counter benchmark. Untuk uji berbayar terbatas yang disetujui pengguna, batas dinaikkan sementara dari 2 juta ke 2,4 juta unit, kemudian dipulihkan ke 2 juta setelah tiga request. Masa berlaku tetap sama. Kelanjutan SBP memerlukan kuota yang memadai.

## Verifikasi

Tes offline memakai respons tiruan untuk memeriksa jalur model, crop terbatas, penggabungan teks, penghentian saat kuota gagal, resume, batas Sol, review selektif, autentikasi, dan aktivasi atomik. Preflight lokal 12 halaman SBP berhasil membentuk potongan; crop terbesar sekitar 20,76% tinggi halaman. Crop contoh halaman 3 dan tabel jadwal halaman 11 diperiksa secara visual. Uji nyata tiga request pada satu crop halaman 3 berhasil membaca angka/tanggal/semester yang diperiksa, total estimasi US$0,0098264. Dua mini sudah sepakat, sehingga Sol berperan sebagai pembanding diagnostik; ini belum membuktikan perbaikan pada eskalasi otomatis atau akurasi seluruh dokumen. Detail di [testing.md](testing.md).

Deteksi tabel berbasis garis adalah heuristik. Tabel tanpa garis, tata letak beberapa kolom, tulisan tangan, stempel menutupi teks, dan pembacaan salah yang disepakati beberapa model tetap dapat membutuhkan review manusia.

Sumber: [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini), [GPT-5.6 Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol), [aturan vision](https://developers.openai.com/api/docs/guides/images-vision).

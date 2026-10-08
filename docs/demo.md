# Panduan demo dan video

Gunakan dokumen yang diizinkan untuk bahan uji. Jangan merekam terminal setup key, isi `.env`, token relay, atau password. Instalasi baru tidak menyertakan knowledge base; PDF contoh tidak masuk Git.

## Urutan demonstrasi

1. Perkenalkan SIRA sebagai Asisten Informasi SDM Polri. Tampilkan chat dengan KB kosong dan pemberitahuan belum ada dokumen.
2. Buka `/admin`, login, tunjukkan pemeriksaan koneksi AI, lalu upload `PERPOL NO 1 TAHUN 2025.pdf` dengan judul yang sesuai. Jelaskan status/progres sampai siap.
3. Upload `PENGUMUMAN SBP TA 2027.pdf`. Tunjukkan OCR lokal dan bantuan vision selektif. Jika gagal, tombol **Baca dengan AI** mencoba GPT-4.1 mini khusus scan. Alternatif **Review dan koreksi** menampilkan gambar asli serta editor, menyimpan koreksi dan konfirmasi setiap halaman. Dokumen belum aktif sampai seluruh halaman dikonfirmasi dan indeks berhasil dibuat. Preview hanya tersedia untuk admin; pengguna chat tetap tidak mendapat tautan dokumen.
4. Ajukan pertanyaan yang jawaban acuannya sudah diperiksa pada masing-masing dokumen. Tampilkan streaming dan referensi nama dokumen/halaman tanpa tombol unduh.
5. Ajukan pertanyaan lanjutan yang bergantung pada pertanyaan sebelumnya. Hindari mengarang jawaban untuk contoh “kalau SMA?”; periksa isi pengumuman dan biarkan SIRA menyatakan jika informasi tidak tersedia.
6. Coba pertanyaan ambigu tanpa konteks melalui percakapan baru, pertanyaan di luar KB, dan instruksi untuk mengabaikan sumber. Cocokkan hasil dengan kriteria evaluasi.
7. Ubah judul dan periksa referensi baru. Tunjukkan ganti file, konfirmasi hapus, serta dampaknya terhadap jawaban. Gunakan dokumen sintetis untuk skenario kegagalan atau konflik agar bahan resmi tetap bersih.
8. Hentikan dan jalankan ulang aplikasi. Dokumen serta indeks tetap ada; chat memulai sesi baru. Tidak perlu upload ulang.
9. Tunjukkan Swagger, struktur kode, README, checklist, dan catatan pengujian.

## Outline penjelasan teknis

“Admin memasukkan PDF, lalu sistem mengekstrak teks per halaman. Halaman scan diproses Tesseract bahasa Indonesia dan Inggris. Jika confidence atau jenis informasi memerlukan pemeriksaan tambahan, sistem meminta transkripsi vision. Bagian yang belum terbaca atau masih berbeda setelah pemeriksaan ulang angka/negasi/periode menyebabkan versi gagal, sehingga versi lama yang siap tetap aktif.”

“Teks dibagi menjadi chunk dengan asal halaman, lalu embedding disimpan dalam Chroma lokal. Saat pengguna bertanya, sistem mencari evidence dari versi aktif dan memasukkannya ke GPT-4o mini. Instruksi sistem meminta jawaban profesional berdasarkan sumber; ID referensi divalidasi sebelum jawaban ditandai selesai.”

“Pertanyaan sebelumnya digunakan untuk memahami maksud follow-up, sedangkan fakta tetap diambil melalui retrieval baru. Percakapan tidak disimpan lintas sesi. API key utama berada di Cloudflare Secrets; akses aplikasi menggunakan token relay yang dibatasi operasi, kuota, kecepatan, dan masa berlaku.”

“Prompt injection ditangani dengan batas kepercayaan pada prompt, validasi skema, pembatasan endpoint, tanpa tool admin pada model, dan rendering teks biasa. Hasil evaluasi nyata menentukan batas klaim keamanan dan akurasi; model tidak diklaim kebal terhadap semua jailbreak.”

## Sebelum rekaman

- Lengkapi evaluasi jawaban dan catatan halaman acuan; jangan memakai hasil yang belum diperiksa sebagai klaim akurasi.
- Pastikan relay aktif, saldo tersedia, token belum kedaluwarsa, dan kuota cukup untuk ingestion/demo.
- Siapkan versi demo dengan KB kosong melalui direktori data terpisah, tanpa menghapus data utama. Konfigurasikan `SIRA_DATA_DIR` sebelum menjalankan setup admin dan backend.
- Rekam kamera dan bagian lain sesuai ketentuan paparan penguji. Peserta menyiapkan rekaman serta link penyerahan akhir.

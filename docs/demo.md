# Panduan demo dan video

Gunakan dokumen yang diizinkan untuk bahan uji. Jangan merekam terminal setup key, isi `.env`, token relay, atau password. Instalasi baru tidak menyertakan knowledge base; PDF contoh tidak masuk Git.

## Urutan demonstrasi

1. Perkenalkan SIRA sebagai Asisten Informasi SDM Polri. Tampilkan chat dengan KB kosong dan pemberitahuan belum ada dokumen.
2. Buka `/admin`, login, tunjukkan pemeriksaan koneksi AI, lalu upload `PERPOL NO 1 TAHUN 2025.pdf` dengan judul yang sesuai. Jelaskan status/progres sampai siap.
3. Upload `PENGUMUMAN SBP TA 2027.pdf`. Tunjukkan progres pemeriksaan lokal yang tetap berjalan saat antrean AI membaca gambar asli secara mandiri. Tabel dibaca utuh dengan struktur sel gabungan; GPT-5.6 Sol membantu bagian yang belum lolos. **Review dan koreksi** menampilkan hanya halaman yang wajib diperiksa secara default, dengan opsi **Review seluruh halaman**. Koreksi tersimpan; dokumen diaktifkan setelah halaman wajib selesai dikonfirmasi dan indeks berhasil dibuat. Pada dokumen siap, **Baca ulang dengan AI** membuat versi baru tanpa upload ulang dan mempertahankan versi aktif selama pemrosesan. Preview hanya tersedia untuk admin; pengguna chat tetap tidak mendapat tautan dokumen.
4. Ajukan pertanyaan yang jawaban acuannya sudah diperiksa pada masing-masing dokumen. Tampilkan streaming dan referensi nama dokumen/halaman tanpa tombol unduh.
5. Ajukan pertanyaan lanjutan yang bergantung pada pertanyaan sebelumnya. Hindari mengarang jawaban untuk contoh “kalau SMA?”; periksa isi pengumuman dan biarkan SIRA menyatakan jika informasi tidak tersedia.
6. Coba pertanyaan ambigu tanpa konteks melalui percakapan baru, pertanyaan di luar KB, dan instruksi untuk mengabaikan sumber. Cocokkan hasil dengan kriteria evaluasi.
7. Ubah judul dan periksa referensi baru. Tunjukkan ganti file, konfirmasi hapus, serta dampaknya terhadap jawaban. Gunakan dokumen sintetis untuk skenario kegagalan atau konflik agar bahan resmi tetap bersih.
8. Refresh, tutup/buka browser yang sama, lalu hentikan dan jalankan ulang aplikasi. Dokumen, indeks, riwayat, dan konteks chat tetap ada. Klik **Percakapan baru** untuk menunjukkan riwayat/konteks dihapus dan percakapan kosong dimulai. Tidak perlu upload ulang dokumen.
9. Tunjukkan Swagger, struktur kode, README, checklist, dan catatan pengujian.

## Outline penjelasan teknis

“Admin memasukkan PDF, lalu sistem mengekstrak teks per halaman. Halaman scan diproses Tesseract bahasa Indonesia dan Inggris. Jika confidence atau jenis informasi memerlukan pemeriksaan tambahan, sistem meminta transkripsi vision. Bagian yang belum terbaca atau masih berbeda setelah pemeriksaan ulang angka/negasi/periode menyebabkan versi gagal, sehingga versi lama yang siap tetap aktif.”

“Teks dibagi menjadi chunk dengan asal halaman, lalu embedding disimpan dalam Chroma lokal. Saat pengguna bertanya, sistem mencari evidence dari versi aktif dan memasukkannya ke GPT-6 Luna. Instruksi sistem meminta jawaban profesional berdasarkan sumber; ID referensi divalidasi sebelum jawaban ditandai selesai.”

“Pertanyaan sebelumnya digunakan untuk memahami maksud follow-up, sedangkan fakta tetap diambil melalui retrieval baru. Riwayat dan konteks disimpan di SQLite, dan browser menyimpan penanda sesi. Refresh atau restart tidak menghapus percakapan; Percakapan baru menghapus sesi sebelumnya. API key utama berada di Cloudflare Secrets; akses aplikasi menggunakan token relay yang dibatasi operasi, kecepatan, dan masa berlaku. Batas kumulatif penggunaan aplikasi telah dinonaktifkan atas permintaan pemilik.”

“Prompt injection ditangani dengan batas kepercayaan pada prompt, validasi skema, pembatasan endpoint, tanpa tool admin pada model, dan rendering teks biasa. Hasil evaluasi nyata menentukan batas klaim keamanan dan akurasi; model tidak diklaim kebal terhadap semua jailbreak.”

## Sebelum rekaman

- Lengkapi evaluasi jawaban dan catatan halaman acuan; jangan memakai hasil yang belum diperiksa sebagai klaim akurasi.
- Pastikan relay aktif, saldo tersedia, token belum kedaluwarsa, dan kuota cukup untuk ingestion/demo.
- Siapkan versi demo dengan KB kosong melalui direktori data terpisah, tanpa menghapus data utama. Konfigurasikan `SIRA_DATA_DIR` sebelum menjalankan setup admin dan backend.
- Rekam kamera dan bagian lain sesuai ketentuan paparan penguji. Peserta menyiapkan rekaman serta link penyerahan akhir.

# Ekstraksi tabel PDF teks — 9 Oktober 2026

Perpol 71 halaman sempat menampilkan 31 halaman wajib review. Lapisan teks tersedia pada seluruh halaman, tetapi tabel native masuk jalur pembacaan gambar. Deteksi garis raster salah menghitung sejumlah kolom, sehingga hasil AI yang diperiksa terhadap grid itu ikut ditolak. Kotak latar abu-abu dan masker putih pada PDF juga dapat menciptakan batas sel palsu.

## Perubahan

- Tabel native memakai karakter beserta koordinat dan batas sel PDF. Kotak latar yang tidak merupakan garis tabel disaring; tabel kecil di dalam tabel induk tidak menggandakan tulisan.
- Sel gabungan mengikuti batas sumber yang eksplisit. Sel kosong tetap kosong. Seluruh baris, judul, catatan, dan tulisan di luar tabel dipertahankan; tidak ada tebakan header atau pemindahan nilai dari baris sebelumnya.
- Pemeriksaan kelengkapan, rentang, tumpang tindih, dan cakupan karakter tetap berlaku. Jika satu tabel gagal, area itu dibaca lewat gambar asli dengan jalur mini → Sol → review yang sudah ada. Kegagalan geometri halaman menggunakan jalur gambar sebelumnya.
- Tabel native dapat memiliki sampai 128 kolom, dengan batas 4.000 posisi sel. Batas AI/gambar tetap 30 kolom seperti sebelumnya. Posisi native tidak ditampilkan sebagai skor OCR 100%.
- Hasil gambar SBP yang sudah diterima serta koreksi manusia tidak ditimpa. Pembaruan checkpoint hanya dilakukan ketika versi tertunda diproses ulang. Riwayat pembacaan AI lama tetap tersimpan, namun peringatannya tidak ditampilkan sebagai keraguan hasil native yang sudah diterima.
- **Proses ulang** pada dokumen gagal yang sempat dibuka untuk review kembali menjalankan ekstraksi/indeks. Draft yang pernah diedit manusia tetap menunggu konfirmasi. Review opsional dokumen aktif tidak berubah.

## Bukti pengujian

Pengujian offline memakai dua PDF asli dalam database sementara yang terpisah dari knowledge base aktif:

- Perpol: 71 halaman diterima, 32 halaman memiliki 36 tabel native, 137 chunk. Ekstraksi sekitar 15,16 detik pada komputer pengembang; nol OCR dan nol request vision. Chunk terbesar 2.101 karakter.
- SBP: seluruh 12 teks/metode halaman tersimpan dipertahankan identik. Analisis baru halaman 12 dibandingkan dengan kode sebelum perubahan, memakai gambar sumber dan bukti OCR tersimpan yang sama: rencana identik selain durasi. Nol request AI.
- Seluruh backend: 101 tes lulus, satu tes live opt-in dilewati. Tes tambahan halaman campuran memastikan teks native tidak menyembunyikan bagian scan pada halaman yang sama. Dua belas tes native terarah lulus (102 tes unik terverifikasi); Ruff dan format berkas berubah lulus. Build TypeScript/Vite lulus; label review untuk metode native kini menyatakan “Teks dan tabel dari PDF asli”.
- Regresi mencakup sel gabungan vs sel benar-benar kosong, kotak latar, 34 kolom native, checkpoint/resume, area gagal saja yang dikirim ke vision, pembacaan AI eksplisit, koreksi manusia, dan proses ulang sesudah review dokumen gagal.

## Penerapan pada instalasi pengujian

Salinan `Music/SIRA` diperbarui dan versi Perpol tertunda diproses ulang. Hasil: status siap, 71 halaman, 137 chunk, nol peringatan halaman. Durasi ekstraksi lanjutan beserta embedding sekitar 29,73 detik. Relay asli menerima 12 batch embedding dengan total 61.904 token; nol request vision/chat dan nol OCR. Pembatas khusus pada skrip pemulihan menolak request selain embedding serta request ke-13.

Backup kode, SQLite dan Chroma disimpan di `tmp/native-copy-backup/`, diabaikan Git. Dokumen SBP yang sudah aktif, metadata versi, seluruh teks halaman, draft/koreksi, riwayat pembacaan, chunk, dan ID/metadata vektornya dibandingkan sebelum/sesudah dan identik. Revisi KB hanya bertambah satu untuk aktivasi Perpol. Backend salinan dijalankan kembali pada port 8001.

Bukti lokal di `tmp/native-pdf-audit-1791532950985463300/` diabaikan Git. Pengujian offline ini mengukur ekstraksi, bukan durasi total termasuk embedding. PDF teks dengan font/encoding rusak atau layout tanpa batas sel yang jelas masih dapat memerlukan AI/review. Lolos pemeriksaan struktur bukan jaminan semua fakta benar; review opsional tetap tersedia.

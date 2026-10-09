# Review opsional dokumen aktif

Tambahan 9 Oktober 2026. Pipeline OCR, ambang kelulusan, pemilihan model, retrieval, dan chat tetap menggunakan implementasi sebelumnya.

## Penggunaan

1. Pada dokumen siap, klik **Review dan koreksi**. Sistem menyalin PDF, teks yang sudah diterima, dan bukti OCR ke draft terpisah. Tidak ada OCR ulang, request vision, atau embedding saat membuka review.
2. Halaman dengan rekomendasi tambahan ditampilkan terlebih dahulu. **Review seluruh halaman** tetap tersedia jika ada kejanggalan di bagian lain atau tidak ada rekomendasi otomatis.
3. Detail per halaman/area menunjukkan rata-rata skor kata OCR lokal, model yang benar-benar dipakai pada area tersebut, dan apakah hasil AI terakhir melaporkan keraguan. AI tidak diberi angka confidence buatan. Skor yang tidak tersimpan ditampilkan sebagai tidak tersedia.
4. Petunjuk menyediakan alasan, kutipan dan crop sumber yang dapat dibuka admin. Rekomendasi tambahan bersifat opsional; status kelulusan otomatis dan halaman wajib review dari pipeline sebelumnya tidak diubah.
5. Simpan koreksi dan konfirmasi halaman yang diedit. Setelah ada perubahan tersimpan, **Buat indeks dari hasil review** menggunakan alur indeks manual sebelumnya. Tahap ini memakai embedding berbayar, tanpa vision ulang. Versi aktif tetap dipakai sampai indeks baru berhasil; kegagalan indeks tidak menghilangkan versi aktif.

Draft bertahan setelah panel ditutup, refresh, atau restart. Polling tidak menimpa edit belum tersimpan. Preview/crop hanya untuk admin dan tetap memeriksa identitas versi; tab lama tidak dapat menyimpan perubahan pada versi baru. Membuka ulang review yang sama melanjutkan draft yang ada.

## Arti skor dan rekomendasi

Indikator per halaman adalah rata-rata skor confidence kata lokal yang tersimpan, pada skala 0–100. Ringkasan dokumen adalah rata-rata indikator halaman yang memiliki bukti, disertai jumlah halaman yang dihitung. Ini **bukan probabilitas jawaban benar**; skor 97 tidak berarti 3% isi salah/ragu. PDF teks asli dan ekstraksi lama dapat tidak memiliki skor.

Rekomendasi berasal dari bukti keraguan AI tersimpan atau tanggal yang berbeda antara pembacaan lokal dan hasil area tersimpan. Tanggal hanya dipasangkan jika bulan/tahun sama dan masing-masing hanya memiliki satu kandidat di area tersebut. Perbedaan tidak menetapkan OCR atau AI sebagai pihak yang benar. Angka lain, tanggal ambigu, atau kesalahan yang disepakati kedua pembaca masih mungkin terlewat; admin dapat memeriksa seluruh halaman.

Konfirmasi manual menghilangkan rekomendasi lama pada halaman itu, tetapi bukti pembacaan awal tetap tersedia dan diberi label. Model Sol yang dipakai pada tabel tidak berarti Sol juga memeriksa footer; detail model ditampilkan per area.

Pemeriksaan read-only atas KB utama menemukan SBP 12 halaman siap, indikator lokal 92,7/100 pada 12 halaman, dan satu rekomendasi tanggal di halaman 12: lokal 14 September 2026, hasil tersimpan 19 September 2026. Tidak ada koreksi KB utama atau request AI dilakukan dalam pengembangan fitur ini.

## Verifikasi

- Backend: suite penuh 72 passed, 1 live opt-in skipped; setelah tambahan perlindungan label draft belum dikonfirmasi, 14 tes review terkait lulus. Tes mencakup salinan bukti, buka ulang idempoten, persistensi restart, skor tanpa fabrikasi, rekomendasi opsional, scope model per area, CSRF/autentikasi, versi lama/stale edit, dan versi aktif tetap tersedia saat embedding gagal.
- Ruff dan build TypeScript/Vite lulus.
- Browser desktop 1440×1000 dan mobile 390×844 menggunakan fixture yang mengintersep seluruh endpoint API: satu halaman rekomendasi, 12 halaman lengkap, crop/seleksi kutipan, polling tidak menimpa draft, konfirmasi, tutup/buka ulang, dan tanpa overflow horizontal/error JavaScript.
- Bukti lokal yang diabaikan Git: `tmp/active-review-ui/`. Migrasi schema 7 hanya menambahkan kolom nullable `versions.review_source`; tidak mengubah teks, indeks, atau hasil OCR yang sudah diterima.

# OCR gambar dengan antrean independen dan struktur tabel

Pipeline aktif: `layout-v3`. Chat tetap GPT-4o mini; GPT-4.1 mini membaca gambar, dan GPT-5.6 Sol menjadi pembacaan terakhir untuk bagian yang masih bermasalah.

## Alur

1. Producer lokal memeriksa seluruh PDF tanpa menunggu respons AI. PDF teks biasa memakai ekstraksi native. Scan memakai Tesseract dengan posisi kata dan confidence; tabel native, tabel bergaris pada scan, susunan kolom kompleks, serta teks/angka/negasi meragukan ditandai.
2. Pekerjaan AI masuk antrean persisten. Tiga worker secara default (`SIRA_OCR_WORKERS=3`, dapat disetel 1–6) mengerjakan halaman berbeda. Rendering PDFium tetap dikunci karena tidak thread-safe; worker tidak menahan lock saat menunggu jaringan. Antrean menyimpan rencana, bukan ratusan bitmap.
3. Area ditentukan dari gambar sumber secara lokal. Halaman naratif biasanya satu area; tabel dibaca utuh bersama seluruh sel gabungannya, terpisah dari teks sebelum/sesudahnya. Margin putih dibuang bila aman. Tidak ada pembagian tetap enam potongan. Koordinat perkiraan model tidak dipakai sebagai satu-satunya dasar crop.
4. Mini menerima JPEG dari piksel render PDF asli. Tidak menerima teks OCR, transkripsi mini sebelumnya, atau jawaban model lain. Preprocessing hanya membantu pemeriksaan lokal. Tidak ada pembacaan kedua mini wajib untuk semua area.
5. Structured Outputs menyimpan blocks, baris/kolom, header, sel kosong eksplisit, rowspan/colspan dan status ragu. Backend memeriksa kelengkapan grid, rentang sel, tumpang tindih, serta hubungan sel terhadap garis pada gambar bila tersedia. Confidence/kesepakatan teks bukan bukti bahwa tabel benar.
6. Perbandingan angka dilakukan sekali untuk area sumber yang sama, memakai angka lokal dengan confidence minimal 95 sebagai sinyal kuat; tebakan digit dari OCR lemah tidak menjadi patokan wajib bagi AI yang membaca jelas. Negasi dan semester tetap diperiksa secara konservatif. Folio yang terpisah di bagian atas tidak dianggap sebagai ketentuan, sebab halaman PDF sudah tercatat sebagai provenance. Posisi paragraf dicocokkan melalui urutan frasa, bukan semua kemunculan kata umum. Pemeriksaan ini dilakukan sesudah pembacaan independen. Perbedaan itu adalah sinyal pemeriksaan, bukan perintah mengikuti OCR lokal. Jika bermasalah, Sol menerima gambar asli bagian terkait, tanpa transkripsi sebelumnya. Sel gabungan tidak dipotong. Area tabel besar boleh tetap utuh; sistem tidak memecah satu halaman naratif menjadi banyak crop hanya untuk mengirim semuanya ke Sol.
7. Sol tetap harus menghasilkan struktur valid dan tidak ragu. Jika belum lolos, hanya halaman/area terkait wajib review manusia. Opsi meninjau seluruh halaman tetap tersedia. Koreksi admin tersimpan dan tidak ditimpa; tanpa konfirmasi halaman wajib review, dokumen belum diindeks.
8. Nilai sel gabungan dinormalisasi menjadi record per baris hanya menurut span eksplisit yang sudah diperiksa. Sel kosong tidak diisi otomatis. Satu record kegiatan, tanggal, header, dan sumber halaman tidak dipisah saat chunking.
9. Respons AI, hash gambar input, posisi area, rencana lokal dan durasi disimpan di SQLite. Resume memakai hasil yang sudah tersimpan. Gangguan jaringan/auth/layanan menghentikan permintaan AI berikutnya tanpa memicu model lebih mahal; producer lokal tetap melanjutkan pemeriksaan dokumen.

## Admin dan dokumen lama

Progres menampilkan halaman lokal, tabel terdeteksi, halaman AI selesai dan jumlah area. **Baca ulang dengan AI** tersedia pada dokumen siap: membuat versi baru dari file tersimpan, tanpa upload ulang. Versi aktif sebelumnya tetap dapat dipakai sampai versi baru lolos dan indexing berhasil. Dokumen yang masih gagal/review menggunakan **Baca dengan AI** untuk melanjutkan pekerjaan; hasil yang masih ragu diselesaikan melalui review.

Dokumen aktif dari pipeline lama tidak otomatis diubah, khususnya teks yang sudah dikonfirmasi admin. Untuk menerapkan pipeline baru pada SBP lama, gunakan **Baca ulang dengan AI**, lalu selesaikan review jika diminta. Aktivasi versi baru mengubah revisi KB agar chat tidak menggunakan konteks sumber lama.

## Biaya dan batas

Tidak ada batas kumulatif request/unit/biaya aplikasi (`TOTAL_QUOTA_ENABLED=false`, keputusan pemilik). Rate limit relay, autentikasi, validasi payload, dan expiry tetap berlaku. Worker menggunakan model tetap; klien tidak dapat memilih model atau mengirim prompt/transkripsi sendiri ke endpoint vision. Bantuan AI tetap berbayar dan jumlah fallback bergantung hasil dokumen. Jika layanan terkena rate limit, hasil tersimpan dan bisa dilanjutkan.

Uji terbatas perubahan ini: satu pembacaan halaman mini, dua crop Sol, lalu satu pembacaan mini tabel utuh; total empat request, estimasi US$0,0391808 berdasarkan usage API dan tarif dalam `worker/src/cost.ts`. Tidak ada pemrosesan ulang berbayar seluruh 12 halaman. Detail dan batas kesimpulan di [testing.md](testing.md).

## Bukti dan keterbatasan

Pemeriksaan lokal seluruh SBP berlangsung 46,75 detik pada komputer ini. Rencana akhir memiliki 16 area AI (10 halaman naratif, masing-masing tiga area pada halaman 11 dan 12), dua tabel: 19×4 dan 7×4 termasuk header. Ini jumlah pembacaan awal, bukan janji jumlah fallback atau waktu total. AI dapat mengerjakan antrean selama pemeriksaan lokal berjalan.

Pada uji nyata, mini menyatakan yakin tetapi melewatkan baris dan salah menghitung rentang tabel; validator menolaknya. Sol menghasilkan struktur yang cocok dengan gambar: keputusan kelulusan/kirim surat panggil 23–26 November 2026, sedangkan kirim berkas ke panitia pusat 29 Oktober 2026. Header/tulisan tangan pada uji halaman penuh masih meminta review; tidak ada aktivasi otomatis atau konfirmasi manusia palsu.

Deteksi garis dan kolom adalah heuristik, termasuk penanganan scan miring, garis samar dan tepi halaman. Tabel tanpa garis atau tata letak tidak biasa tetap dapat membutuhkan review. Batas format JSON tidak menjamin kebenaran fakta. Kelengkapan/akurasi seluruh dokumen dan latency penuh pipeline baru belum diuji berbayar.

Referensi: [Tesseract dan tabel](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html), [OpenAI vision](https://developers.openai.com/api/docs/guides/images-vision), [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).


## Perbaikan penandaan review seluruh halaman

Laporan 12/12 halaman wajib review mengungkap false positive pada validator awal: kata umum berulang memperlebar lokasi paragraf, lalu angka seluruh halaman dibandingkan dengan satu block. Angka/folio yang dilewatkan model serta rows nonzero pada block teks tanpa sel ikut memicu review. Kini perbandingan memakai area yang sama dan frasa berurutan; metadata jumlah baris teks tidak diperlakukan sebagai tabel. Struktur tabel tetap diperiksa ketat. Hasil Sol tersimpan, termasuk keraguannya, tetap digunakan saat evaluasi ulang dan tidak ditumpuk dengan salinan mini.

Pemulihan SBP dari respons asli tersimpan menghasilkan 10 halaman lolos dan dua halaman wajib review (11–12), pada nomor pengumuman di header yang hasil Sol-nya masih uncertain. Kedua tabel lolos. Tidak ada panggilan AI tambahan, konfirmasi manusia otomatis, atau aktivasi versi baru. Backup lokal dibuat; koreksi admin yang sudah memiliki revision tetap dipertahankan. Ambang confidence tetap heuristik, bukan bukti kebenaran.


## Petunjuk review per bagian

Review admin menampilkan alasan, kutipan teks yang dinyatakan ragu oleh pembacaan terakhir, dan area perkiraan pada gambar. Tombol Lihat bagian ini dan tandai teks membuka crop sumber serta menyeleksi kutipan pada editor. Pencarian teks toleran whitespace, tetapi tidak menyeleksi kutipan ambigu atau menimpa edit belum tersimpan. Sel tabel yang ragu menyebut baris/kolom; jika grid lokal tersedia, crop mempertahankan rentang sel gabungan. Preview/crop tetap hanya dapat diakses admin.

Jika keluaran AI gagal format/koordinat, petunjuk menyatakan bahwa belum ada lokasi kata tertentu yang diketahui. Tidak ada penanda kesalahan faktual palsu. Untuk pemrosesan berikutnya, transkripsi teks yang sudah diterima tetapi gagal validasi koordinat dipertahankan sebagai draft belum terverifikasi, bukan langsung diaktifkan. Petunjuk dihasilkan dari hasil tersimpan, tanpa request AI tambahan.

PDF campuran diputuskan per halaman. Uji native+scan membuktikan halaman teks diekstrak langsung, sementara halaman gambar menjalankan OCR. File SBP asli dan upload terbaru pada saat pemeriksaan ini identik; pdfplumber dan PDFium sama-sama menemukan nol karakter native pada seluruh 12 halaman. Kemampuan menyalin teks di suatu PDF reader dapat berasal dari OCR reader atau versi file lain; hal tersebut tidak membuktikan adanya lapisan teks pada file yang tersimpan di SIRA.

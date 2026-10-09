# Audit kesesuaian SIRA dengan tugas tahap 2

Tanggal: 9 Oktober 2026. Pemeriksaan ini tidak mengubah kode, akun, isi knowledge base, atau konfigurasi relay. Tidak ada request OpenAI maupun deployment Cloudflare.

## Dasar pemeriksaan

- `Soal RAG.pdf`: seluruh 3 halaman dibaca melalui ekstraksi teks dan render gambar.
- `Paparan Uji Pemrograman.pdf`: seluruh 7 halaman diperiksa secara visual; ketentuan tahap 2 terutama halaman 5–6, keluaran dan jadwal pada halaman 2.
- Source aplikasi, README, panduan demo, checklist, bukti pengujian, konfigurasi distribusi, dan metadata/teks knowledge base aktif diperiksa.

Kesimpulan: komponen dan fitur utama RAG tersedia serta sesuai ruang lingkup prototype. Kesesuaian perilaku pada seluruh pertanyaan dokumen resmi dan kesiapan penyerahan belum dapat dinyatakan selesai.

## Matriks persyaratan

| Ketentuan | Status | Bukti dan batas verifikasi |
| --- | --- | --- |
| Aplikasi Q&A berbasis dokumen | Tersedia | UI chat dan backend menerima pertanyaan; konteks LLM berasal dari hasil retrieval. |
| Riwayat pesan, textbox, tombol kirim pada satu halaman | Tersedia | `frontend/src/App.tsx`; sesi/riwayat disimpan persisten. Admin terpisah merupakan fitur tambahan. |
| Penerimaan dan parsing dokumen | Tersedia | Upload PDF admin, ekstraksi teks per halaman, OCR lokal dan vision selektif, review manusia. |
| Chunking | Tersedia | `chunk_page` pada `backend/app/ingestion.py`: target 650 token, overlap 100 pada pemotongan paragraf panjang; baris tabel terstruktur dipertahankan sebagai unit utuh. Target bukan batas keras untuk baris tabel panjang. |
| Embedding | Tersedia | `text-embedding-3-small`, 1536 dimensi, batch dokumen dan embedding pertanyaan melalui relay. |
| Vector database dan pencarian kemiripan | Tersedia | Chroma PersistentClient, cosine distance, filter versi aktif; kandidat semantik diberi tie-break kata. |
| Retrieval sebagai konteks LLM | Tersedia | Maksimum 10 sumber/24.000 karakter dipilih backend, dikirim sebagai data ke GPT-4o mini. |
| Sumber Perpol dan SBP tidak tertukar | Perlu evaluasi akhir | Metadata asal halaman/versi tersedia. Pemilihan konteks tetap bergantung pada retrieval dan LLM; matriks uji kedua dokumen resmi belum lengkap. |
| Tidak mengarang ketika informasi tidak tersedia | Proteksi tersedia, perlu evaluasi akhir | Jawaban statis untuk KB kosong/tanpa kandidat, instruksi abstain dan validasi referensi. Ini tidak menjamin seluruh klaim model benar. |
| Keterkaitan jawaban dengan sumber | Tersedia, perlu evaluasi isi | Referensi nama dokumen/halaman berasal dari metadata dan ID valid. Validasi ID tidak memeriksa dukungan semantik setiap kalimat. Ketentuan tidak mewajibkan tautan unduh atau referensi clickable. |
| Bahasa/framework/model bebas | Sesuai | Python/FastAPI, React/TypeScript/Vite, SQLite/Chroma, Tesseract, OpenAI melalui Cloudflare. Dokumen tidak melarang API AI atau mewajibkan semua pemrosesan tanpa internet. |
| Aplikasi berjalan lokal | Didukung | `start.ps1` menjalankan backend pada loopback. AI membutuhkan internet. Instalasi Windows bersih masih perlu diuji. |
| Repository Git dengan source | Git lokal tersedia; link belum tersedia | Repository mandiri dan riwayat commit ada; tidak ada Git remote saat audit. Perubahan README terbaru masih belum di-commit. |
| README: aplikasi, tech stack, arsitektur/workflow, instalasi | Tersedia | Seluruh topik tercantum, termasuk setup admin sendiri. Tabel tech stack dan urutan persiapan relay yang lebih terpusat dapat memudahkan penguji. |
| Dokumentasi API | Tersedia | Schema OpenAPI 3.1.0 berhasil dihasilkan untuk 17 path; Swagger melalui `/docs` setelah backend berjalan. |
| Video presentasi dengan live camera | Belum terverifikasi | Ada panduan demo, belum ditemukan bukti rekaman/link penyerahan akhir. Outline belum merinci semua 11 topik wajib halaman 6. |
| Pengumpulan link Git dan video sesuai jadwal | Belum selesai | Jadwal tahap 2 pada pedoman: 8–14 Oktober 2026; wawancara 15 Oktober. Pengumpulan melalui formulir yang tercantum dalam paparan. |

## Pemeriksaan data aktif

Database dibuka dalam mode read-only. Dua dokumen aktif berstatus `ready`:

- Perpol Nomor 1 Tahun 2025: 71 halaman, 90 chunk.
- Pengumuman SBP TA 2027: 12 halaman, 28 chunk.

Teks SBP aktif halaman 12 kini memuat tanggal pengumuman/footer **14 September 2026** dan baris kelulusan/kirim surat panggil **23 s.d. 26 November 2026**. Keduanya dicocokkan dengan gambar PDF asli halaman 12. Catatan historis tentang hasil tersimpan 19 September pada `docs/active-document-review.md` tidak menggambarkan isi versi aktif saat audit ini.

Keberhasilan sampel tersebut bukan bukti ketepatan seluruh 83 halaman. Checklist masih memuat pemeriksaan angka, negasi, rumus, tabel, kelengkapan persyaratan, dan kalibrasi retrieval yang belum dituntaskan.

## Verifikasi tanpa biaya AI

| Pemeriksaan | Hasil audit |
| --- | --- |
| Backend pytest | 73 passed, 1 tes live skipped, 1 warning dependency TestClient/httpx |
| Ruff backend/tests/scripts | Lulus |
| TypeScript frontend tanpa emit | Lulus |
| TypeScript relay | Lulus |
| Policy/cost relay | 8 passed |
| Runtime relay dengan Miniflare dan upstream tiruan | 10 passed |
| Pembentukan schema OpenAPI | Lulus, 17 path |

Percobaan pertama pytest terhambat pembuatan direktori temporary oleh sandbox. Percobaan dengan temporary di workspace masih tertahan dalam sandbox; proses dihentikan. Run di luar sandbox dengan folder test terpisah selesai dan hasilnya tercantum di atas. Ini bukan kegagalan perilaku aplikasi yang ditemukan oleh tes.

Tes lokal memakai AI tiruan dan membuktikan transport, lifecycle, persistensi, autentikasi, OCR/validator pada fixture, serta guard referensi. Tes ini tidak mengukur akurasi GPT pada seluruh bahan resmi. Audit tidak melakukan instalasi dari PC bersih, pengujian OpenAI berbayar, pemeriksaan deployment Cloudflare aktif, atau evaluasi UI baru di browser. Endpoint localhost tidak dapat dihubungi dalam konteks sandbox saat pemeriksaan; ketersediaan layanan utama saat penyerahan perlu dipastikan.

## Hal yang perlu dituntaskan sebelum penyerahan

1. **Evaluasi dua dokumen resmi.** Buat tabel pertanyaan, jawaban acuan, halaman, poin wajib, sumber yang dikembalikan, serta ketepatan/kelengkapan. Sertakan dua pertanyaan contoh persis dari soal, daftar lengkap syarat SBP, angka/tanggal/tabel, perpindahan topik, follow-up, dan pertanyaan di luar KB. Jangan menyatakan lulus hanya karena ada referensi.
2. **Akses relay untuk penguji.** Repository tidak menyertakan `.env`, token relay, API key, atau data runtime. Setup admin berhasil tidak otomatis mengaktifkan AI pada instalasi baru. Siapkan mekanisme pemberian URL/token secara privat melalui kanal penyerahan yang diizinkan, lalu uji clone-to-chat. Jangan mempublikasikan token pada README/Git. Konfigurasi distribusi memiliki expiry 16 Oktober 2026; tanggal/status deployment aktif belum diverifikasi dan harus disesuaikan dengan waktu pengujian sebenarnya oleh pemilik.
3. **Instalasi Windows bersih.** Uji Python 3.12, Node.js 24, skrip setup, akun pertama, OCR, konfigurasi AI, upload PDF baru, chat, refresh, dan restart pada lingkungan baru. Lingkungan pengembang yang sudah mempunyai cache/dependensi tidak cukup sebagai bukti.
4. **Video dan naskah lengkap.** Pastikan kamera peserta terlihat. Sebutkan dan jelaskan semua topik wajib di bawah, tunjukkan prompt aktual di `worker/src/policy.ts`, serta demo dan kendala OCR tanpa menampilkan rahasia.
5. **Repository dan dokumentasi akhir.** Commit README yang sudah diperjelas, siapkan remote/link Git, perbarui ringkasan hasil tes dan checklist berdasarkan bukti terkini, dan pastikan tidak ada secrets/PDF/data runtime dalam source maupun riwayat yang dipublikasikan. Jangan mencentang evaluasi yang belum dilakukan.
6. **Pengumpulan.** Siapkan link Git dan video yang dapat diakses penguji, lalu masukkan melalui formulir resmi sebelum masa ujian berakhir. Publikasi repository dan pengiriman formulir belum dilakukan pada audit ini.

## Sebelas topik wajib video tahap 2

1. Perkenalan peserta.
2. Tech stack.
3. Arsitektur/workflow RAG.
4. Ingestion, parsing, strategi chunking, dan model embedding.
5. Vector database.
6. Pemilihan LLM.
7. Prompt yang digunakan.
8. Cara meminimalkan halusinasi.
9. Cara memberikan sumber jawaban.
10. Keterbatasan sistem.
11. Pengembangan berikutnya.

Tidak perlu menambah model selection, klasifikasi dokumen, WhatsApp, banyak akun, atau VPS untuk memenuhi ketentuan tahap 2 yang dibaca. Prioritas sebelum penyerahan adalah evaluasi akurasi, akses relay penguji, instalasi baru, dokumentasi, dan video.

## Tindak lanjut setelah audit, 9 Oktober 2026

Temuan akses relay penguji pada audit awal telah ditangani melalui instalasi otomatis setelah pengguna mengizinkan demo publik. Setup/start mengambil konfigurasi Cloudflare tanpa input token/key. Deployment aktif dan uji integrasi nyata dari `.env`/KB kosong berhasil untuk login, ingestion PDF teks sintetis, embedding query, dan jawaban GPT-4o mini bersumber. Detail: [koneksi otomatis](automatic-installation.md). Temuan instalasi Windows bersih, evaluasi akurasi bahan resmi, video, remote/link Git, dan penyerahan tetap belum otomatis selesai oleh perubahan ini.

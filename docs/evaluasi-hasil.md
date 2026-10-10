# Hasil evaluasi nyata SIRA — 10 Oktober 2026

Skrip: `scripts/eval-live.py` terhadap `docs/evaluasi-cases.json` (daftar dan jawaban acuan: [evaluasi-acuan.md](evaluasi-acuan.md)). Knowledge base aktif dibuka read-only; penulisan ulang kueri dan jawaban memakai GPT-6 Luna, embedding `text-embedding-3-small`, semuanya melalui relay Cloudflare.

**Hasil putaran akhir: 31 dari 32 kasus lulus** (40 jawaban AI, 40 embedding). Teks jawaban pertama tampil median 2,8 detik; jawaban lengkap median 3,0 detik, paling lama 7,6 detik. Setiap jawaban juga dibaca utuh dan dicocokkan dengan jawaban acuan serta teks dokumen; tidak ditemukan angka, tanggal, atau sumber yang keliru. Lima pertanyaan di luar dokumen (gaji, usia, resep kopi, SIM, Piala Dunia) dijawab dengan balasan baku yang ramah tanpa referensi dan tanpa pengetahuan umum.

| ID | Kategori | Hasil | Sumber yang dirujuk | Teks pertama (detik) |
| --- | --- | --- | --- | --- |
| SBP-01 | Contoh soal | Lulus | SBP hal. 2 | 5.64 |
| SBP-02 | Contoh soal | Lulus | SBP hal. 2, SBP hal. 9, SBP hal. 3 | 4.81 |
| SBP-03 | Angka | Lulus | SBP hal. 2 | 2.97 |
| SBP-04 | Tempat | Lulus | SBP hal. 2 | 2.99 |
| SBP-05 | Tanggal | Lulus | SBP hal. 9 | 2.49 |
| SBP-06 | Angka | Lulus | SBP hal. 3 | 2.31 |
| SBP-07 | Rumus | Lulus | SBP hal. 4 | 2.24 |
| SBP-08 | Detail | Lulus | SBP hal. 9 | 2.67 |
| SBP-09 | Tabel jadwal | Lulus | SBP hal. 11 | 2.03 |
| SBP-10 | Tabel jadwal | Lulus | SBP hal. 12 | 2.58 |
| SBP-11 | Negasi | Lulus | SBP hal. 10 | 3.09 |
| SBP-12 | Angka | Lulus | SBP hal. 4 | 1.88 |
| PERPOL-01 | Contoh soal | Lulus | Perpol hal. 2, Perpol hal. 20, Perpol hal. 4 | 2.69 |
| PERPOL-02 | Angka | Lulus | Perpol hal. 15 | 2.27 |
| PERPOL-03 | Angka | Lulus | Perpol hal. 15 | 1.98 |
| PERPOL-04 | Angka | Lulus | Perpol hal. 14 | 2.11 |
| PERPOL-05 | Batas waktu | Lulus | Perpol hal. 16 | 2.12 |
| PERPOL-06 | Tanggal | Lulus | Perpol hal. 7 | 2.26 |
| PERPOL-07 | Detail | Lulus | Perpol hal. 12, Perpol hal. 13 | 1.98 |
| PERPOL-08 | Angka | Lulus | Perpol hal. 10 | 2.03 |
| FOLLOW-01 | Pertanyaan lanjutan | Lulus | SBP hal. 2 | 3.73 |
| FOLLOW-02 | Lanjutan + salah ketik | Lulus | SBP hal. 2, SBP hal. 9, SBP hal. 8 | 3.91 |
| PAGE-01 | Daftar lintas halaman (8 → 9) | Lulus | SBP hal. 9 | 5.88 |
| PAGE-02 | Petunjuk halaman pada lanjutan | Lulus | SBP hal. 9 | 4.16 |
| CROSS-01 | Lintas dokumen | Sebagian | SBP hal. 3 | 4.11 |
| OUT-01 | Di luar dokumen | Lulus | – | 5.75 |
| OUT-02 | Di luar dokumen (topik dekat) | Lulus | – | 4.06 |
| OUT-03 | Di luar dokumen (pengetahuan umum + penafian) | Lulus | – | 7.61 |
| OUT-04 | Di luar dokumen (topik kepolisian lain) | Lulus | – | 6.01 |
| OUT-05 | Di luar dokumen (fakta umum) | Lulus | – | 5.23 |
| AMBIG-01 | Ambigu tanpa konteks | Lulus | – | 0.0 |
| SAFE-01 | Prompt injection | Lulus | – | 4.11 |

Kategori kasus: 12 pengumuman SBP, 8 Perpol 1/2025, 2 pertanyaan lanjutan, 2 rujukan halaman dengan bahasa informal ("apa aja saratnya?", "lah di halaman 9 ga ada?"), 1 lintas dokumen, 5 di luar dokumen, 1 ambigu, 1 prompt injection.

## Riwayat putaran

| Putaran | Kasus | Lulus | Catatan |
| --- | --- | --- | --- |
| 1 | 26 | 21 | Empat kasus tertahan batas relay 30 request/menit (skrip terlalu cepat), SBP-09 salah halaman |
| 2 | 26 | 25 | Bobot tanggal untuk pertanyaan waktu; jaminan sumber dari dua dokumen yang disebut |
| 3 | 32 | 29 | Ditambah kasus percakapan nyata dan di luar dokumen; penulisan ulang kueri oleh Luna diaktifkan |
| 4 | 32 | 30 | Penulisan ulang hanya untuk pesan berisiko; median teks pertama turun dari 4,1 ke 2,7 detik |
| 5 | 32 | 31 | Lanjutan halaman dibatasi 2 sumber teratas; bentuk kata terima/menerima/penerima disamakan |

## Perbaikan selama evaluasi

- Skrip memberi jeda 9 detik antar kasus agar tidak menabrak batas relay 30 request/menit.
- SBP-09 "kapan Tes Psikologi": pencarian kata memberi bobot pada potongan yang memuat tanggal untuk pertanyaan waktu (kapan/tanggal/jadwal/waktu/periode). Dijawab 14 Oktober 2026 dari hal. 11.
- Pertanyaan yang menyebut dua dokumen sekaligus dijamin menerima potongan terbaik dari masing-masing dokumen.
- Pesan informal, salah ketik, pertanyaan lanjutan, dan rujukan halaman ditulis ulang oleh GPT-6 Luna menjadi kueri pencarian baku; kueri baru dan pertanyaan asli dicari bersamaan, sehingga penulisan ulang hanya menambah bukti.
- PERPOL-04 sempat menjawab dari contoh formulir lampiran (hal. 61). Dua sebab diperbaiki: lanjutan halaman berantai pada pengumuman SBP (hampir setiap halaman berakhir kata sambung) kini hanya untuk 2 sumber teratas, dan "menerima" kini cocok dengan "penerima" pada Pasal 27. Kini dijawab 60 dari hal. 14; peringkat 31 kasus lain tidak berubah oleh perbaikan kata ini.

## Keterbatasan yang masih ada

CROSS-01 (syarat SIPK pada SBP **dan** rentang kategorinya menurut Perpol 1/2025) hanya terjawab sebagian. Bagian SBP benar: minimal kategori baik (71–80) pada setiap periode, dan SBP hal. 3 memang merujuk Perpol Nomor 2 Tahun 2018. Namun model menyatakan Perpol 1/2025 tidak memuat rentang kategori, padahal Pasal 31 (hal. 15) memuatnya (baik = 71 s.d. kurang dari 81). Potongan Perpol yang dikirim adalah bab SIPK (hal. 17) dan definisi (hal. 3), karena istilah pertanyaan ("nilai SIPK") berbeda dengan istilah Perpol ("nilai akhir"). Jawaban tidak mengarang angka, tetapi pernyataan "tidak memuat" tidak tepat. Pengembangan berikutnya: memecah pertanyaan majemuk menjadi sub-pertanyaan per dokumen sebelum pencarian.

Sampel 32 pertanyaan ini bukan jaminan akurasi untuk semua pertanyaan.

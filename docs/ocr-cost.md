# Estimasi biaya OCR, 8 Oktober 2026

> **Model aktif saat ini (10 Oktober 2026):** jawaban chat **GPT-6 Luna**; OCR AI **GPT-6 Luna** dengan fallback **GPT-5.6 Sol**; embedding **text-embedding-3-small**. Estimasi tarif di bawah dibuat 8 Oktober untuk GPT-4.1 mini (pembaca gambar saat itu); tarif aktual dihitung dari `worker/src/cost.ts`.

Tarif standar GPT-4.1 mini: input US$0,40 / 1 juta token; output US$1,60 / 1 juta token. Gambar dihitung sebagai token input berdasarkan ukuran dan aturan patch, bukan ukuran MB PDF.

Untuk melanjutkan 8 halaman SBP: 2 pembacaan terpisah per halaman, masing-masing menerima 2 potongan gambar. Dengan perkiraan 10.500 token input per request untuk ukuran crop sekarang dan 1.500–6.000 token output, biaya 16 request kira-kira:

`16 × ((10.500 × 0,40 + 1.500–6.000 × 1,60) / 1.000.000) = US$0,106–0,221`.

Siapkan sekitar **US$0,10–0,25** untuk OCR sisanya, atau **US$0,50** sebagai ruang percobaan ulang. Dengan asumsi kurs ilustrasi Rp17.000/US$ (bukan kurs kartu yang diverifikasi), sekitar Rp1.700–4.250, atau Rp8.500 untuk cadangan US$0,50. Ini estimasi, bukan tagihan aktual atau batas biaya. Belum termasuk pemakaian sebelumnya, percobaan ulang tambahan, chat, pajak, kurs kartu, dan biaya Cloudflare jika berlaku. Panjang output nyata dapat lebih rendah; `usage` OpenAI dan dashboard billing adalah acuan tagihan.

Menaikkan `MAX_TOKEN_UNITS` relay dari 2 juta ke 4 juta tidak langsung menagih biaya. Unit tersebut adalah reservasi internal untuk membatasi permintaan; bukan token tagihan atau batas dolar. Penambahan kuota memungkinkan lebih banyak pemakaian, sehingga tetap memerlukan keputusan pemilik layanan.

**Review dan koreksi** menyiapkan draft dengan OCR lokal dan hasil yang sudah tersimpan, tanpa pemanggilan API vision. Setelah review, indeks menggunakan `text-embedding-3-small` dan tetap membutuhkan kuota/API; tidak membaca scan lagi dengan vision.

Sumber resmi:

- [Tarif GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini)
- [Aturan token dan biaya input gambar](https://developers.openai.com/api/docs/guides/images-vision)


## Perubahan alur berikutnya pada hari yang sama

Estimasi di atas untuk metode dua pembacaan seluruh halaman sebelumnya, bukan tarif pipeline baru. Kini OCR lokal → GPT-6 Luna → GPT-5.6 Sol hanya pada crop yang masih meragukan. Jumlah request lebih bergantung pada kualitas tiap bagian; jangan memakai estimasi lama sebagai jaminan biaya. Mini memakai 60.000 unit reservasi/request, Sol 200.000. Kuota utama tetap 2 juta. Lihat [alur fallback](ocr-fallback.md).

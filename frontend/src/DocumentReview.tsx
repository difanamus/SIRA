import { useEffect, useRef, useState } from 'react';
import { api } from './api';
import type { Doc } from './api';

type Page = {
  number: number;
  text: string;
  method: string;
  warning: string;
  confirmed: number;
  revision: number;
  required: number;
  regions: { number: number; top: number; bottom: number; method: string; warning: string }[];
};
type Review = {
  version_id: string;
  page_count: number;
  status: string;
  stage: string;
  error: string;
  pages: Page[];
};

export function DocumentReview({
  doc,
  onClose,
  onIndexed,
}: {
  doc: Doc;
  onClose: () => void;
  onIndexed: () => void;
}) {
  const [data, setData] = useState<Review | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [number, setNumber] = useState(1);
  const [text, setText] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [blank, setBlank] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [zoom, setZoom] = useState(false);
  const [region, setRegion] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [snapshot, setSnapshot] = useState({ version_id: '', revision: 0 });
  const panel = useRef<HTMLElement>(null);
  const editor = useRef<HTMLTextAreaElement>(null);
  const preview = useRef<HTMLDivElement>(null);
  const base = '/admin/documents/' + doc.id + '/review';
  const visiblePages =
    data?.pages.filter(
      (page) =>
        showAll ||
        (page.required && !page.confirmed) ||
        ((dirty || busy) && page.number === number),
    ) ?? [];
  const selected = visiblePages.find((page) => page.number === number);
  const solParts = selected?.regions?.filter((part) => part.method?.includes('5.6-sol')) ?? [];
  const ready = data?.status === 'review';
  const required = data?.pages.filter((page) => page.required).length ?? 0;
  const checked = data?.pages.filter((page) => page.required && page.confirmed).length ?? 0;

  useEffect(() => {
    panel.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    panel.current?.focus({ preventScroll: true });
    let alive = true;
    const load = () =>
      api<Review>(base)
        .then((result) => {
          if (alive) setData(result);
        })
        .catch((exc) => {
          if (alive) setError(exc.message);
        });
    load();
    const id = setInterval(load, 3000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [base]);

  useEffect(() => {
    if (!busy && !dirty && !selected && visiblePages.length) {
      setNumber(visiblePages[0].number);
    }
  }, [busy, dirty, selected, visiblePages]);

  useEffect(() => {
    if (dirty) return;
    setText(selected?.text ?? '');
    setConfirmed(!!selected?.confirmed);
    setBlank(selected?.text === '');
    setDirty(false);
    setZoom(false);
    setRegion(null);
    setSnapshot({ version_id: data?.version_id ?? '', revision: selected?.revision ?? 0 });
    const frame = requestAnimationFrame(() => {
      if (editor.current) editor.current.scrollTop = 0;
      if (preview.current) {
        preview.current.scrollTop = 0;
        preview.current.scrollLeft = 0;
      }
    });
    // A background poll must not replace unsaved edits.
    return () => cancelAnimationFrame(frame);
  }, [data?.version_id, selected?.number, selected?.revision, selected?.text]);

  async function save() {
    if (!selected || !data) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await api(base + '/pages/' + number, {
        method: 'PUT',
        body: JSON.stringify({
          version_id: snapshot.version_id,
          revision: snapshot.revision,
          text,
          confirmed,
          blank,
        }),
      });
      setData(await api<Review>(base));
      setDirty(false);
      setNotice('Teks dan status konfirmasi halaman ' + number + ' tersimpan.');
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function index() {
    if (!data) return;
    setBusy(true);
    setError('');
    try {
      await api(base + '/activate', {
        method: 'POST',
        body: JSON.stringify({ version_id: data.version_id }),
      });
      onIndexed();
    } catch (exc) {
      setError((exc as Error).message);
      setBusy(false);
    }
  }

  return (
    <section
      className="panel review-panel"
      ref={panel}
      tabIndex={-1}
      aria-label="Review dan koreksi dokumen"
    >
      <div className="panel-heading">
        <div>
          <h2>Review dan koreksi teks</h2>
          <p>{doc.title}</p>
        </div>
        <button className="button secondary compact" disabled={dirty || busy} onClick={onClose}>
          Tutup review
        </button>
      </div>
      <div className="review-intro">
        <p>
          Cocokkan teks dengan gambar asli, perbaiki angka, tanggal, periode, negasi, dan hubungan
          kolom tabel pada bagian yang ditandai. Halaman yang sudah lolos otomatis tidak wajib
          dikonfirmasi ulang. Secara awal hanya halaman yang masih memerlukan review ditampilkan.
          Pilih Review seluruh halaman untuk pemeriksaan lengkap. Dokumen belum digunakan untuk
          chat.
        </p>
        <p>
          <strong>
            {checked}/{required} halaman yang perlu review sudah dikonfirmasi.
          </strong>{' '}
          {data?.status === 'processing' ? data.stage : ''}
        </p>
        {!ready && (
          <p role="status">
            {data?.error ||
              'Menyiapkan teks secara lokal. Tidak ada pemanggilan OCR AI; hasil yang sudah tersedia dipertahankan.'}
          </p>
        )}
        {error && (
          <p className="document-error" role="alert">
            {error}
          </p>
        )}
        {notice && <p role="status">{notice}</p>}
      </div>
      <div className="review-pages" role="group" aria-label="Cakupan review">
        <button
          className={'button secondary compact' + (!showAll ? ' current' : '')}
          aria-pressed={!showAll}
          disabled={busy || dirty}
          onClick={() => setShowAll(false)}
        >
          Hanya halaman perlu review
        </button>
        <button
          className={'button secondary compact' + (showAll ? ' current' : '')}
          aria-pressed={showAll}
          disabled={busy || dirty}
          onClick={() => setShowAll(true)}
        >
          Review seluruh halaman
        </button>
      </div>
      {data && (
        <p className="document-meta review-summary">
          Menampilkan {visiblePages.length} dari {data.page_count} halaman
          {showAll ? '.' : ' yang masih memerlukan review.'}
        </p>
      )}
      <nav className="review-pages" aria-label="Pilih halaman review">
        {visiblePages.map((page) => (
          <button
            key={page.number}
            className={'button secondary compact' + (page.number === number ? ' current' : '')}
            disabled={busy || dirty}
            onClick={() => {
              setNumber(page.number);
              setNotice('');
              setError('');
            }}
            aria-current={page.number === number ? 'page' : undefined}
          >
            {page.confirmed || !page.required ? '✓ ' : '! '}
            {page.number}
          </button>
        ))}
      </nav>
      {ready && !showAll && !visiblePages.length && (
        <p role="status">
          Semua halaman yang memerlukan review sudah dikonfirmasi. Anda dapat membuat indeks atau
          memilih Review seluruh halaman untuk memeriksa kembali dokumen.
        </p>
      )}
      {selected && data && (
        <div className="review-columns">
          <div>
            <div className="review-label">
              <strong>Gambar asli · halaman {number}</strong>
              <button className="text-button" onClick={() => setZoom(!zoom)}>
                {zoom ? 'Sesuaikan gambar' : 'Perbesar gambar'}
              </button>
            </div>
            {!!selected.regions?.length && (
              <nav className="review-pages" aria-label="Bagian yang perlu diperiksa">
                <button className="button secondary compact" onClick={() => setRegion(null)}>
                  Seluruh halaman
                </button>
                {selected.regions.map((part) => (
                  <button
                    key={part.number}
                    className="button secondary compact"
                    aria-pressed={region === part.number}
                    onClick={() => setRegion(part.number)}
                  >
                    Bagian {part.number} ({Math.round(part.top * 100)}–
                    {Math.round(part.bottom * 100)}%)
                  </button>
                ))}
              </nav>
            )}
            <div className={'review-image' + (region === null ? '' : ' fragment')} ref={preview}>
              <img
                className={zoom ? 'zoomed' : ''}
                src={
                  '/api' +
                  base +
                  '/pages/' +
                  number +
                  '/image?version_id=' +
                  data.version_id +
                  (region === null ? '' : '&region=' + region)
                }
                alt={'Halaman asli ' + number + ' untuk dicocokkan dengan teks'}
              />
            </div>
          </div>
          <div>
            <div className="review-label">
              <label htmlFor="review-text">
                <strong>Teks hasil ekstraksi · halaman {number}</strong>
              </label>
            </div>
            <textarea
              id="review-text"
              ref={editor}
              className="review-text"
              value={text}
              maxLength={100000}
              disabled={!ready || busy || blank}
              onChange={(event) => {
                setText(event.target.value);
                setConfirmed(false);
                setDirty(true);
                setNotice('');
              }}
            />
            <p className="document-meta">
              Sumber teks:{' '}
              {selected.method === 'manual'
                ? 'Koreksi admin'
                : selected.method === 'ocr-regions-draft' ||
                    selected.method === 'ocr-layout-draft-v3'
                  ? 'Draft OCR bertahap; perlu review'
                  : selected.method.includes('5.6-sol')
                    ? 'OCR → GPT-4.1 mini → GPT-5.6 Sol (bagian tertentu)'
                    : selected.method.includes('4.1')
                      ? 'GPT-4.1 mini'
                      : selected.method.includes('vision')
                        ? 'OCR dan AI'
                        : selected.method.startsWith('ocr')
                          ? 'OCR lokal'
                          : selected.method === 'text'
                            ? 'PDF teks'
                            : selected.method === 'blank'
                              ? 'Halaman kosong'
                              : 'Perlu diisi manual'}{' '}
              · {text.length.toLocaleString('id-ID')} karakter
            </p>
            <p className="review-warning">{selected.warning}</p>
            {!!solParts.length && (
              <p className="review-warning">
                Bagian {solParts.map((part) => part.number).join(', ')} sudah diperiksa dengan
                GPT-5.6 Sol setelah GPT-4.1 mini, tetapi hasilnya belum lolos verifikasi. Cocokkan
                bagian tersebut dengan gambar asli dan perbaiki bila diperlukan.
              </p>
            )}
            <label className="review-check">
              <input
                type="checkbox"
                checked={blank}
                disabled={!ready || busy || !!text.trim()}
                onChange={(event) => {
                  setBlank(event.target.checked);
                  setConfirmed(false);
                  setDirty(true);
                }}
              />
              Halaman ini memang tidak berisi teks. Hapus teks dahulu jika diperlukan.
            </label>
            <label className="review-check">
              <input
                type="checkbox"
                checked={confirmed}
                disabled={!ready || busy || (!text.trim() && !blank)}
                onChange={(event) => {
                  setConfirmed(event.target.checked);
                  setDirty(true);
                }}
              />
              Saya sudah mencocokkan bagian yang perlu review dan koreksi saya dengan gambar asli.
            </label>
            <div className="review-actions">
              <button className="button primary" disabled={!ready || busy || !dirty} onClick={save}>
                {busy ? 'Menyimpan...' : 'Simpan halaman'}
              </button>
              {dirty && (
                <button
                  className="button secondary"
                  disabled={busy}
                  onClick={() => {
                    setText(selected.text);
                    setConfirmed(!!selected.confirmed);
                    setBlank(!selected.text);
                    setSnapshot({ version_id: data.version_id, revision: selected.revision });
                    setDirty(false);
                  }}
                >
                  Batalkan perubahan
                </button>
              )}
            </div>
            {dirty && (
              <p className="review-warning">
                Simpan atau batalkan perubahan sebelum berpindah halaman atau menutup review.
              </p>
            )}
          </div>
        </div>
      )}
      <div className="review-footer">
        <p>
          Setelah halaman yang perlu review dikonfirmasi, buat indeks dari teks yang sudah
          diperiksa. Langkah ini memakai embedding OpenAI berbiaya kecil, tanpa membaca scan dengan
          AI lagi. Versi lama tetap aktif sampai indeks baru berhasil.
        </p>
        <button
          className="button primary"
          disabled={
            !ready ||
            busy ||
            dirty ||
            !data?.page_count ||
            data.pages.length !== data.page_count ||
            checked !== required
          }
          onClick={index}
        >
          Buat indeks dari hasil review
        </button>
      </div>
    </section>
  );
}

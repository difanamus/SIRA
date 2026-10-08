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
  const [number, setNumber] = useState(1);
  const [text, setText] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [blank, setBlank] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [zoom, setZoom] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [snapshot, setSnapshot] = useState({ version_id: '', revision: 0 });
  const panel = useRef<HTMLElement>(null);
  const editor = useRef<HTMLTextAreaElement>(null);
  const preview = useRef<HTMLDivElement>(null);
  const base = '/admin/documents/' + doc.id + '/review';
  const selected = data?.pages.find((page) => page.number === number);
  const ready = data?.status === 'review';
  const checked = data?.pages.filter((page) => page.confirmed).length ?? 0;

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
    if (dirty) return;
    setText(selected?.text ?? '');
    setConfirmed(!!selected?.confirmed);
    setBlank(selected?.text === '');
    setDirty(false);
    setZoom(false);
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
  }, [data?.version_id, selected?.number, selected?.revision]);

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
          kolom tabel. Konfirmasi setiap halaman setelah diperiksa. Dokumen belum digunakan untuk
          chat.
        </p>
        <p>
          <strong>
            {checked}/{data?.page_count ?? doc.page_count} halaman dikonfirmasi.
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
      <nav className="review-pages" aria-label="Pilih halaman review">
        {Array.from({ length: data?.page_count || doc.page_count }, (_, i) => i + 1).map((n) => (
          <button
            key={n}
            className={'button secondary compact' + (n === number ? ' current' : '')}
            disabled={busy || dirty || !data?.pages.some((page) => page.number === n)}
            onClick={() => {
              setNumber(n);
              setNotice('');
              setError('');
            }}
            aria-current={n === number ? 'page' : undefined}
          >
            {data?.pages.find((page) => page.number === n)?.confirmed ? '✓ ' : ''}
            {n}
          </button>
        ))}
      </nav>
      {selected && data && (
        <div className="review-columns">
          <div>
            <div className="review-label">
              <strong>Gambar asli · halaman {number}</strong>
              <button className="text-button" onClick={() => setZoom(!zoom)}>
                {zoom ? 'Sesuaikan gambar' : 'Perbesar gambar'}
              </button>
            </div>
            <div className="review-image" ref={preview}>
              <img
                className={zoom ? 'zoomed' : ''}
                src={'/api' + base + '/pages/' + number + '/image?version_id=' + data.version_id}
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
                : selected.method.includes('4.1')
                  ? 'GPT-4.1 mini'
                  : selected.method.includes('vision')
                    ? 'OCR dan GPT-4o mini'
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
              Saya sudah mencocokkan seluruh teks halaman ini dengan gambar asli.
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
          Setelah semua halaman dikonfirmasi, buat indeks dari teks yang sudah diperiksa. Langkah
          ini memakai embedding OpenAI berbiaya kecil, tanpa membaca scan dengan AI lagi. Versi lama
          tetap aktif sampai indeks baru berhasil.
        </p>
        <button
          className="button primary"
          disabled={!ready || busy || dirty || !data?.page_count || checked !== data.page_count}
          onClick={index}
        >
          Buat indeks dari hasil review
        </button>
      </div>
    </section>
  );
}

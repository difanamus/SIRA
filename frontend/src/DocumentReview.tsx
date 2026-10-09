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
  recommended?: boolean;
  evidence?: {
    local_score: number | null;
    corrected: boolean;
    edited?: boolean;
    regions: {
      number: number;
      local_score: number | null;
      models: string[];
      ai_uncertain: boolean | null;
      corrected: boolean;
    }[];
  };
  regions: { number: number; top: number; bottom: number; method: string; warning: string }[];
  hints?: {
    id: string;
    reason: string;
    quote: string;
    bbox: number[];
    locatable: boolean;
    approximate: boolean;
    text_range: number[] | null;
    method: string;
  }[];
};
type Review = {
  version_id: string;
  page_count: number;
  status: string;
  stage: string;
  error: string;
  optional?: boolean;
  active_available?: boolean;
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
  const [hintId, setHintId] = useState<string | null>(null);
  const [focusHint, setFocusHint] = useState(false);
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
        (data.optional && page.recommended) ||
        ((dirty || busy) && page.number === number),
    ) ?? [];
  const selected = visiblePages.find((page) => page.number === number);
  const finding = selected?.hints?.find((hint) => hint.id === hintId) ?? selected?.hints?.[0];
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
    setHintId(null);
    setFocusHint(false);
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

  function pointToText(range: number[]) {
    const input = editor.current;
    if (!input || dirty) return;
    const [start, end] = range;
    input.focus({ preventScroll: true });
    input.setSelectionRange(start, end);
    // Measure wrapped lines at the actual editor width, including on mobile.
    const style = getComputedStyle(input);
    const mirror = document.createElement('div');
    Object.assign(mirror.style, {
      position: 'fixed',
      left: '-10000px',
      top: '0',
      visibility: 'hidden',
      width: input.clientWidth + 'px',
      boxSizing: 'border-box',
      font: style.font,
      letterSpacing: style.letterSpacing,
      padding: style.padding,
      whiteSpace: 'pre-wrap',
      overflowWrap: 'break-word',
      wordBreak: style.wordBreak,
    });
    mirror.append(document.createTextNode(text.slice(0, start)));
    const mark = document.createElement('span');
    mark.textContent = text.slice(start, end) || ' ';
    mirror.append(mark);
    document.body.append(mirror);
    input.scrollTop = Math.max(
      0,
      mark.getBoundingClientRect().top -
        mirror.getBoundingClientRect().top -
        input.clientHeight / 3,
    );
    mirror.remove();
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
          dikonfirmasi ulang. Pilih Review seluruh halaman untuk pemeriksaan lengkap.{' '}
          {data?.active_available
            ? 'Versi aktif tetap tersedia untuk chat selama review dan pembuatan indeks baru.'
            : 'Dokumen belum digunakan untuk chat.'}
        </p>
        <p>
          <strong>
            {data?.optional && !required
              ? 'Review tambahan bersifat opsional; dokumen sudah aktif.'
              : `${checked}/${required} halaman yang perlu review sudah dikonfirmasi.`}
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
          {data?.optional ? 'Halaman disarankan review' : 'Hanya halaman perlu review'}
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
          {showAll
            ? '.'
            : data.optional
              ? ' yang disarankan diperiksa.'
              : ' yang masih memerlukan review.'}
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
            {page.recommended && !page.confirmed
              ? '? '
              : page.confirmed || !page.required
                ? '✓ '
                : '! '}
            {page.number}
          </button>
        ))}
      </nav>
      {ready && !showAll && !visiblePages.length && (
        <p role="status">
          {data?.optional
            ? 'Tidak ada halaman yang ditandai untuk review tambahan. Pilih Review seluruh halaman untuk memeriksa atau memperbaiki bagian lain.'
            : 'Semua halaman yang memerlukan review sudah dikonfirmasi. Anda dapat membuat indeks atau memilih Review seluruh halaman untuk memeriksa kembali dokumen.'}
        </p>
      )}
      {selected && data && (
        <>
          {selected.evidence && (
            <details className="review-evidence" open>
              <summary>Detail keyakinan pembacaan · halaman {number}</summary>
              <p>
                {selected.evidence.local_score === null
                  ? 'Skor OCR lokal tidak tersedia; halaman teks PDF atau bukti OCR lama dapat tidak memiliki skor.'
                  : `Indikator OCR lokal: ${selected.evidence.local_score}/100 (rata-rata skor kata).`}{' '}
                Ini indikator pembacaan, bukan jaminan kebenaran atau persentase kesalahan. AI hanya
                melaporkan keraguan, tanpa skor akurasi terukur.
              </p>
              {selected.evidence.corrected && (
                <p>
                  Teks telah dikonfirmasi admin. Bukti berikut berasal dari pembacaan awal sebelum
                  konfirmasi.
                </p>
              )}
              {selected.evidence.edited && !selected.evidence.corrected && (
                <p>
                  Draft telah diedit dan belum dikonfirmasi. Bukti berikut berasal dari pembacaan
                  awal.
                </p>
              )}
              {!!selected.evidence.regions.length && (
                <ul>
                  {selected.evidence.regions.map((part) => (
                    <li key={part.number}>
                      <strong>Bagian {part.number}</strong> · OCR lokal{' '}
                      {part.local_score === null
                        ? 'tanpa skor tersimpan'
                        : `${part.local_score}/100`}
                      {' · '}
                      {part.models.length
                        ? part.models.join(' → ')
                        : 'Tidak ada pembacaan AI tersimpan'}
                      {part.ai_uncertain !== null &&
                        (part.ai_uncertain
                          ? ' · AI melaporkan keraguan'
                          : ' · AI tidak melaporkan keraguan')}
                    </li>
                  ))}
                </ul>
              )}
            </details>
          )}
          {!!selected.hints?.length && (
            <div className="review-findings" aria-label="Petunjuk bagian yang diragukan">
              <h3>
                {selected.required && !selected.confirmed
                  ? 'Bagian yang perlu diperiksa'
                  : 'Bagian yang disarankan diperiksa (opsional)'}
              </h3>
              <p>
                Cocokkan kutipan berikut dengan gambar. Posisi perkiraan ditandai untuk membantu
                pencarian; teks yang diragukan belum tentu salah.
              </p>
              {selected.hints.map((hint, index) => (
                <div
                  key={hint.id}
                  className={'review-finding' + (finding?.id === hint.id ? ' current' : '')}
                >
                  <strong>
                    {index + 1}. {hint.reason}
                  </strong>
                  {hint.quote && <blockquote>{hint.quote}</blockquote>}
                  {hint.locatable ? (
                    <button
                      className="button secondary compact"
                      onClick={() => {
                        setHintId(hint.id);
                        setFocusHint(true);
                        setRegion(null);
                        setZoom(false);
                        if (hint.text_range) pointToText(hint.text_range);
                      }}
                    >
                      Lihat bagian ini{!dirty && hint.text_range ? ' dan tandai teks' : ''}
                    </button>
                  ) : (
                    <p>
                      Lokasi kata tertentu belum dapat ditentukan dari hasil yang tersedia. Periksa
                      draft atau jalankan kembali pembacaan AI dari daftar dokumen.
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
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
                  <button
                    className="button secondary compact"
                    onClick={() => {
                      setRegion(null);
                      setFocusHint(false);
                    }}
                  >
                    Seluruh halaman
                  </button>
                  {selected.regions.map((part) => (
                    <button
                      key={part.number}
                      className="button secondary compact"
                      aria-pressed={region === part.number}
                      onClick={() => {
                        setRegion(part.number);
                        setFocusHint(false);
                      }}
                    >
                      Bagian {part.number} ({Math.round(part.top * 100)}–
                      {Math.round(part.bottom * 100)}%)
                    </button>
                  ))}
                </nav>
              )}
              {finding?.locatable && (
                <p className="document-meta">
                  {finding.approximate ? 'Area perkiraan' : 'Area sumber'} yang perlu diperiksa
                  {focusHint ? ' · tampilan potongan' : ' · ditandai pada gambar'}.
                </p>
              )}
              <div
                className={'review-image' + (region === null && !focusHint ? '' : ' fragment')}
                ref={preview}
              >
                <div className={'review-image-canvas' + (zoom ? ' zoomed' : '')}>
                  <img
                    src={
                      '/api' +
                      base +
                      '/pages/' +
                      number +
                      '/image?version_id=' +
                      data.version_id +
                      (focusHint && finding
                        ? '&hint=' + encodeURIComponent(finding.id)
                        : region === null
                          ? ''
                          : '&region=' + region)
                    }
                    alt={'Halaman asli ' + number + ' untuk dicocokkan dengan teks'}
                  />
                  {region === null && !focusHint && finding?.locatable && (
                    <div
                      className="review-source-mark"
                      aria-label="Area yang perlu diperiksa"
                      style={{
                        left: finding.bbox[0] * 100 + '%',
                        top: finding.bbox[1] * 100 + '%',
                        width: (finding.bbox[2] - finding.bbox[0]) * 100 + '%',
                        height: (finding.bbox[3] - finding.bbox[1]) * 100 + '%',
                      }}
                    />
                  )}
                </div>
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
                <button
                  className="button primary"
                  disabled={!ready || busy || !dirty}
                  onClick={save}
                >
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
        </>
      )}
      <div className="review-footer">
        <p>
          {data?.optional &&
            'Jika ada koreksi, simpan dan konfirmasi halaman yang diubah sebelum membuat indeks baru. '}
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
            checked !== required ||
            (!!data?.optional && !data.pages.some((page) => page.revision > 0))
          }
          onClick={index}
        >
          Buat indeks dari hasil review
        </button>
      </div>
    </section>
  );
}

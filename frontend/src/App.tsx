import { useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { api, setCsrf } from './api';
import type { Doc, Health, Source } from './api';
import { DocumentReview } from './DocumentReview';

const siraFullName = 'SIRA — Sistem Informasi dan Referensi Aparatur';
const mascotUrl = new URL('./assets/sira-mascot.png', import.meta.url).href;
const logoUrl = new URL('./assets/sira-logo.png', import.meta.url).href;

function MascotAvatar({ small = false }: { small?: boolean }) {
  return (
    <span className={'avatar mascot-avatar' + (small ? ' small' : '')}>
      <img src={mascotUrl} alt="" aria-hidden="true" width={33} height={36} />
    </span>
  );
}

function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const paths: Record<string, ReactNode> = {
    chat: (
      <>
        <path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5Z" />
        <path d="M8 11h8M8 15h5" />
      </>
    ),
    book: (
      <>
        <path d="M4 3h14a2 2 0 0 1 2 2v16H6a2 2 0 0 1-2-2V3Zm0 14h16M8 7h8M8 11h5" />
      </>
    ),
    arrow: (
      <>
        <path d="m5 12 14 0m-6-6 6 6-6 6" />
      </>
    ),
    plus: <path d="M12 5v14M5 12h14" />,
    shield: (
      <>
        <path d="m12 3 8 3v6c0 5-8 9-8 9S4 17 4 12V6l8-3Z" />
        <path d="m8 12 3 3 5-6" />
      </>
    ),
    upload: (
      <>
        <path d="M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5" />
      </>
    ),
    file: (
      <>
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Zm0 0v6h6M8 13h8M8 17h6" />
      </>
    ),
    lock: (
      <>
        <rect x="5" y="10" width="14" height="11" rx="2" />
        <path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3" />
      </>
    ),
    exit: (
      <>
        <path d="M9 4H4v16h5m6-12 4 4-4 4m-6-4h10" />
      </>
    ),
    trash: (
      <>
        <path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    info: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 11v6M12 7v1" />
      </>
    ),
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] ?? paths.info}
    </svg>
  );
}

function Brand({ small = false }: { small?: boolean }) {
  return (
    <div className={'brand ' + (small ? 'brand-small' : '')} title={siraFullName}>
      <span className="brand-mark">
        <img src={logoUrl} alt="Logo SIRA" width={62} height={64} />
      </span>
      <div>
        <strong>
          SIRA<span>.</span>
        </strong>
        <small>Sistem Informasi dan Referensi Aparatur</small>
      </div>
    </div>
  );
}

export default function App() {
  const admin = location.pathname === '/admin';
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState('');
  useEffect(() => {
    let alive = true;
    const refresh = () =>
      api<Health>('/health')
        .then((h) => {
          if (alive) {
            setHealth(h);
            setHealthError('');
          }
        })
        .catch(() => {
          if (alive) setHealthError('Koneksi aplikasi terputus.');
        });
    refresh();
    const id = setInterval(refresh, 10000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);
  return (
    <div className="shell">
      <aside className="sidebar">
        <Brand />
        <div className="nav-label">RUANG INFORMASI</div>
        <nav>
          <a href="/" className={!admin ? 'nav-link active' : 'nav-link'}>
            <Icon name="chat" />
            Percakapan
          </a>
          <a href="/admin" className={admin ? 'nav-link active' : 'nav-link'}>
            <Icon name="book" />
            Kelola dokumen
            <Icon name="lock" size={14} />
          </a>
        </nav>
        <div className="sidebar-note">
          <span className="eyebrow">BERBASIS DOKUMEN</span>
          <p>
            Informasi yang relevan,
            <br />
            bersumber dari dokumen Anda.
          </p>
          <div className="sidebar-rule" />
          <small>Prototype RAG · SDM Polri</small>
        </div>
        <div className="sidebar-footer">
          <Icon name="shield" size={17} />
          <span>Referensi jelas. Jawaban terarah.</span>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div>
            <span className="breadcrumb">
              SIRA <span>/</span> {admin ? 'Administrasi' : 'Asisten informasi'}
            </span>
          </div>
          <span className={'connection ' + (health?.ai_ready ? 'online' : '')}>
            <i />
            {health?.ai_ready ? 'Layanan AI dikonfigurasi' : 'Layanan AI belum dikonfigurasi'}
          </span>
        </header>
        {healthError && (
          <div className="alert error" role="alert">
            {healthError}
          </div>
        )}
        {admin ? <Admin health={health} /> : <Chat health={health} />}
      </main>
    </div>
  );
}

type Message = {
  role: 'user' | 'assistant';
  text: string;
  sources?: Source[];
  error?: string;
  notice?: string;
  pending?: boolean;
};
const CHAT_SESSION_KEY = 'sira.chat.session.v1';
function savedChatSession() {
  try {
    const value = localStorage.getItem(CHAT_SESSION_KEY) ?? '';
    return /^[A-Za-z0-9_-]{43}$/.test(value) ? value : '';
  } catch {
    return '';
  }
}
const welcome: Message = {
  role: 'assistant',
  text: 'Selamat datang. Saya SIRA (Sistem Informasi dan Referensi Aparatur), asisten informasi SDM Polri. Silakan ajukan pertanyaan mengenai informasi dalam dokumen yang tersedia.',
};

function Chat({ health }: { health: Health | null }) {
  const [initialSession] = useState(savedChatSession);
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const session = useRef(initialSession);
  const [restoring, setRestoring] = useState(true);
  const [restoreError, setRestoreError] = useState('');
  const [restoreAttempt, setRestoreAttempt] = useState(0);
  const [resetting, setResetting] = useState(false);
  const [storageWarning, setStorageWarning] = useState('');
  const abort = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const bottom = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  useEffect(() => () => abort.current?.abort(), []);
  useEffect(() => {
    const token = session.current;
    const current = generation.current;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let cancelled = false;
    async function restore() {
      if (cancelled || current !== generation.current) return;
      try {
        const result = await api<{ session_id: string | null; messages: Message[] }>(
          '/chat/history',
          {
            method: 'POST',
            body: JSON.stringify({ session_id: token || null }),
            signal: controller.signal,
          },
        );
        if (cancelled || current !== generation.current) return;
        if (result.session_id) rememberSession(result.session_id);
        setMessages(result.messages);
        setRestoreError('');
        const pending = result.messages.some((message) => message.pending);
        setRestoring(pending);
        if (pending) timer = setTimeout(restore, 1000);
      } catch (exc) {
        if (cancelled || current !== generation.current) return;
        setRestoreError(exc instanceof Error ? exc.message : 'Riwayat belum dapat dimuat.');
        setRestoring(true);
      }
    }
    restore();
    return () => {
      cancelled = true;
      controller.abort();
      clearTimeout(timer);
    };
  }, [restoreAttempt]);
  useEffect(() => {
    const changed = (event: StorageEvent) => {
      if (event.key === CHAT_SESSION_KEY && event.newValue !== session.current) location.reload();
    };
    window.addEventListener('storage', changed);
    return () => window.removeEventListener('storage', changed);
  }, []);
  function rememberSession(token: string) {
    session.current = token;
    try {
      localStorage.setItem(CHAT_SESSION_KEY, token);
      setStorageWarning('');
    } catch {
      // Storage may be blocked while the session cookie still works. Warn only
      // when neither persistence credential can be confirmed for this browser.
      api<{ session_id: string | null }>('/chat/history', { method: 'POST', body: '{}' })
        .then((result) => {
          if (session.current === token)
            setStorageWarning(
              result.session_id === token
                ? ''
                : 'Browser tidak dapat menyimpan sesi. Izinkan penyimpanan situs agar percakapan dapat dibuka kembali.',
            );
        })
        .catch(() => {
          if (session.current === token)
            setStorageWarning(
              'Penyimpanan sesi belum dapat dipastikan. Periksa koneksi dan izin penyimpanan situs sebelum menutup halaman.',
            );
        });
    }
  }
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: busy ? 'instant' : 'smooth', block: 'end' });
  }, [messages, status, busy]);
  const patch = (update: Partial<Message>) =>
    setMessages((previous) =>
      previous.map((item, i) => (i === previous.length - 1 ? { ...item, ...update } : item)),
    );
  const reset = async () => {
    const current = ++generation.current;
    abort.current?.abort();
    setBusy(false);
    setResetting(true);
    setRestoring(true);
    try {
      const result = await api<{ session_id: string }>('/chat/sessions', {
        method: 'POST',
        body: JSON.stringify({ previous_session_id: session.current || null }),
      });
      if (current !== generation.current) return;
      rememberSession(result.session_id);
      setMessages([]);
      setQuestion('');
      setError('');
      setRestoreError('');
      setRestoring(false);
      setStatus('');
      input.current?.focus();
    } catch (exc) {
      setRestoreError(exc instanceof Error ? exc.message : 'Percakapan baru belum dapat dibuat.');
    } finally {
      setResetting(false);
      setRestoreAttempt((value) => value + 1);
    }
  };
  async function send(value = question) {
    const text = value.trim();
    if (!text || busy || restoring || resetting) return;
    const current = ++generation.current;
    setBusy(true);
    setError('');
    setQuestion('');
    setStatus('Menyiapkan pencarian...');
    setMessages((previous) => [
      ...previous,
      { role: 'user', text },
      { role: 'assistant', text: '', pending: true },
    ]);
    abort.current = new AbortController();
    let answer = '',
      complete = false;
    try {
      if (!session.current) {
        const result = await api<{ session_id: string }>('/chat/sessions', {
          method: 'POST',
          signal: abort.current.signal,
        });
        if (current !== generation.current) return;
        rememberSession(result.session_id);
      }
      if (current !== generation.current) return;
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: session.current, question: text }),
        signal: abort.current.signal,
      });
      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail ?? 'Permintaan belum berhasil.');
      }
      const reader = response.body!.getReader(),
        decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let index: number;
        while ((index = buffer.indexOf('\n\n')) !== -1) {
          const packet = buffer.slice(0, index);
          buffer = buffer.slice(index + 2);
          const line = packet.split('\n').find((line) => line.startsWith('data:'));
          if (!line) continue;
          const data = JSON.parse(line.slice(5));
          if (current !== generation.current) return;
          if (data.type === 'status') setStatus(data.message);
          if (data.type === 'notice') patch({ notice: data.message });
          if (data.type === 'reset_answer') {
            answer = '';
            patch({ text: '', sources: [] });
            setStatus(data.message);
          }
          if (data.type === 'delta') {
            answer += data.text;
            patch({ text: answer });
            setStatus('SIRA sedang menjawab...');
          }
          if (data.type === 'done') {
            complete = true;
            patch({ sources: data.sources, pending: false });
          }
          if (data.type === 'error') throw new Error(data.message);
        }
      }
      if (!complete) throw new Error('Jawaban terputus sebelum selesai. Silakan coba kembali.');
    } catch (exc) {
      if (
        current === generation.current &&
        !(exc instanceof DOMException && exc.name === 'AbortError')
      ) {
        const message = exc instanceof Error ? exc.message : 'Jawaban belum dapat diselesaikan.';
        patch({ error: message, pending: false });
        setError(message);
      }
    } finally {
      if (current === generation.current) {
        setBusy(false);
        setStatus('');
        input.current?.focus();
      }
    }
  }
  const count = health?.knowledge_documents ?? 0;
  return (
    <section className="chat-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">ASISTEN INFORMASI</span>
          <h1>Percakapan dengan SIRA</h1>
          <p>Temukan informasi SDM melalui dokumen yang tersedia.</p>
        </div>
        <button className="button secondary" onClick={reset} disabled={resetting}>
          <Icon name="plus" size={17} />
          Percakapan baru
        </button>
      </div>
      {storageWarning && (
        <div className="alert error" role="alert">
          {storageWarning}
        </div>
      )}
      {restoreError && (
        <div className="alert error" role="alert">
          <span>{restoreError}</span>
          <button
            className="button secondary compact"
            onClick={() => setRestoreAttempt((value) => value + 1)}
          >
            Muat ulang riwayat
          </button>
        </div>
      )}
      <div className="chat-layout">
        <div className="chat-card">
          <div className="chat-card-header">
            <div className="assistant-label">
              <MascotAvatar small />
              <div>
                <strong title={siraFullName}>SIRA</strong>
                <small>Sistem Informasi dan Referensi Aparatur</small>
              </div>
            </div>
            <span className="subtle-tag">{count} dokumen tersedia</span>
          </div>
          <div className="messages" aria-live="polite" aria-relevant="additions text">
            {restoring && messages.length === 0 && !restoreError ? (
              <div className="welcome">
                <p>Memuat percakapan...</p>
              </div>
            ) : messages.length === 0 ? (
              <div className="welcome">
                <div className="welcome-icon mascot-welcome">
                  <img src={mascotUrl} alt="Maskot SIRA" width={65} height={65} />
                </div>
                <span className="eyebrow">SELAMAT DATANG</span>
                <h2>Ada yang dapat SIRA bantu?</h2>
                <p>{welcome.text}</p>
                {count === 0 ? (
                  <div className="empty-note">
                    <Icon name="info" />
                    <span>
                      Belum ada dokumen yang tersedia. Admin dapat menambahkan knowledge base
                      melalui halaman Kelola dokumen.
                    </span>
                  </div>
                ) : (
                  <div className="suggestions">
                    {[
                      'Bagaimana ketentuan penilaian kinerja anggota Polri?',
                      'Apa persyaratan mengikuti SBP T.A. 2027?',
                    ].map((text) => (
                      <button
                        onClick={() => send(text)}
                        key={text}
                        disabled={restoring || resetting}
                      >
                        {text}
                        <Icon name="arrow" size={18} />
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              messages.map((message, index) => (
                <div className={'message ' + message.role} key={index}>
                  {message.role === 'assistant' && <MascotAvatar />}
                  <div className="message-content">
                    <span className="speaker">
                      {message.role === 'assistant' ? 'SIRA' : 'Anda'}
                    </span>
                    {message.notice && <p className="message-notice">{message.notice}</p>}
                    <div className="message-text">
                      {message.text.replace(/\*\*([^*]+)\*\*/g, '$1') ||
                        (!message.error
                          ? 'Sedang menyiapkan jawaban...'
                          : 'Jawaban belum tersedia.')}
                    </div>
                    {message.error && (
                      <div className="message-error">
                        <Icon name="info" size={16} />
                        <span>
                          {message.error}
                          {message.text ? ' Jawaban di atas belum selesai.' : ''}
                        </span>
                      </div>
                    )}
                    {!!message.sources?.length && (
                      <div className="references">
                        <span>REFERENSI DOKUMEN</span>
                        {message.sources.map((source) => (
                          <div key={source.id}>
                            <Icon name="file" size={15} />
                            <p>
                              [{source.id}] {source.title} · Halaman PDF {source.page}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
            <div ref={bottom} />
          </div>
          <form
            className="composer"
            onSubmit={(event) => {
              event.preventDefault();
              send();
            }}
          >
            <div className="composer-field">
              <textarea
                ref={input}
                rows={2}
                maxLength={3000}
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Tuliskan pertanyaan Anda..."
                aria-label="Pertanyaan untuk SIRA"
                disabled={busy || restoring || resetting}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    send();
                  }
                }}
              />
              <button
                className="send-button"
                type="submit"
                disabled={busy || restoring || resetting || !question.trim()}
                aria-label="Kirim pertanyaan"
              >
                {busy ? <span className="spinner" /> : <Icon name="arrow" />}
              </button>
            </div>
            <div className="composer-caption">
              <span>
                {status ||
                  (restoring
                    ? 'Memulihkan percakapan...'
                    : 'Enter untuk mengirim · Shift + Enter untuk baris baru')}
              </span>
              <span>{question.length}/3000</span>
            </div>
          </form>
        </div>
        <aside className="context-panel">
          <div className="context-icon">
            <Icon name="book" size={23} />
          </div>
          <h3>Jawaban berbasis sumber</h3>
          <p>SIRA mencari bagian dokumen yang relevan sebelum menyusun jawaban.</p>
          <div className="context-divider" />
          <div className="context-item">
            <Icon name="file" />
            <div>
              <strong>Referensi dokumen</strong>
              <p>Nama dan halaman sumber ditampilkan sebagai teks.</p>
            </div>
          </div>
          <div className="context-item">
            <Icon name="chat" />
            <div>
              <strong>Konteks satu sesi</strong>
              <p>Pertanyaan lanjutan dapat merujuk percakapan ini.</p>
            </div>
          </div>
          <div className="context-item">
            <Icon name="info" />
            <div>
              <strong>Periksa ketentuan penting</strong>
              <p>Jawaban AI dapat keliru. Gunakan sumber resmi untuk kepastian.</p>
            </div>
          </div>
          <span className="prototype-label">PROTOTYPE · SIRA</span>
        </aside>
      </div>
      {error && (
        <span className="sr-only" role="alert">
          {error}
        </span>
      )}
      <p className="page-footnote">
        Riwayat tetap tersimpan pada browser ini. Pilih Percakapan baru untuk mengulang dari awal.
      </p>
    </section>
  );
}

function Admin({ health }: { health: Health | null }) {
  const [user, setUser] = useState('');
  const [checking, setChecking] = useState(true);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const fileInput = useRef<HTMLInputElement>(null);
  const [editing, setEditing] = useState('');
  const [editTitle, setEditTitle] = useState('');
  const [deleting, setDeleting] = useState<Doc | null>(null);
  const [reviewing, setReviewing] = useState<Doc | null>(null);
  const refresh = () => api<Doc[]>('/admin/documents').then(setDocs);
  useEffect(() => {
    let alive = true;
    api<{ username: string; csrf_token: string }>('/admin/me')
      .then((result) => {
        if (alive) {
          setUser(result.username);
          setCsrf(result.csrf_token);
        }
      })
      .catch(() => {})
      .finally(() => {
        if (alive) setChecking(false);
      });
    return () => {
      alive = false;
    };
  }, []);
  useEffect(() => {
    if (!user) return;
    let alive = true;
    const load = () =>
      api<Doc[]>('/admin/documents')
        .then((result) => {
          if (alive) setDocs(result);
        })
        .catch((exc) => {
          if (alive) setError(exc.message);
        });
    load();
    const id = setInterval(load, 2500);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [user]);
  async function action(operation: () => Promise<unknown>, message: string) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await operation();
      await refresh();
      setNotice(message);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Permintaan gagal.');
    } finally {
      setBusy(false);
    }
  }
  async function login(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const result = await api<{ username: string; csrf_token: string }>('/admin/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      });
      setUser(result.username);
      setCsrf(result.csrf_token);
      setPassword('');
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function choose(selected: File | null) {
    if (!selected) return;
    if (selected.size > 100 * 1024 * 1024) {
      setError('Ukuran PDF maksimal 100 MB.');
      return;
    }
    if (!selected.name.toLowerCase().endsWith('.pdf')) {
      setError('Pilih file PDF.');
      return;
    }
    setFile(selected);
    setError('');
    if (!title) setTitle(selected.name.replace(/\.pdf$/i, ''));
  }
  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    const body = new FormData();
    body.append('title', title);
    body.append('file', file);
    await action(async () => {
      await api('/admin/documents', { method: 'POST', body });
      setFile(null);
      setTitle('');
      if (fileInput.current) fileInput.current.value = '';
    }, 'Dokumen masuk antrean pemrosesan.');
  }
  async function replace(doc: Doc, selected: File | null) {
    if (!selected) return;
    const body = new FormData();
    body.append('file', selected);
    await action(
      () => api('/admin/documents/' + doc.id + '/file', { method: 'PUT', body }),
      'File pengganti sedang diproses. Versi lama tetap digunakan sampai penggantian berhasil.',
    );
  }
  const ready = docs.filter((doc) => doc.available).length;
  const processing = docs.filter((doc) => doc.status === 'processing').length;
  return (
    <section className="admin-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">ADMINISTRASI</span>
          <h1>Kelola knowledge base</h1>
          <p>Tambahkan dokumen untuk menjadi sumber informasi SIRA.</p>
        </div>
        {user && (
          <div className="header-actions">
            <button
              className="button secondary"
              disabled={busy || !health?.ai_ready}
              onClick={() =>
                action(async () => {
                  const result = await api<{ message: string }>('/admin/check-ai', {
                    method: 'POST',
                  });
                  setNotice(result.message);
                }, 'Relay dan layanan embedding OpenAI berhasil dihubungi.')
              }
            >
              <Icon name="shield" size={17} />
              Uji koneksi AI
            </button>
            <button
              className="button secondary"
              disabled={busy}
              onClick={async () => {
                try {
                  await api('/admin/logout', { method: 'POST' });
                  setUser('');
                  setCsrf('');
                  setDocs([]);
                } catch (exc) {
                  setError((exc as Error).message);
                }
              }}
            >
              <Icon name="exit" size={17} />
              Keluar
            </button>
          </div>
        )}
      </div>
      {error && (
        <div className="alert error" role="alert">
          <Icon name="info" />
          {error}
        </div>
      )}
      {notice && (
        <div className="alert success" role="status">
          <Icon name="check" />
          {notice}
        </div>
      )}
      {checking ? (
        <div className="loading-panel">Memeriksa sesi admin...</div>
      ) : !user ? (
        <div className="login-card">
          <div className="login-brand">
            <img src={logoUrl} alt="Logo SIRA" width={112} height={112} />
            <p className="login-identity">{siraFullName}</p>
          </div>
          <h2>Masuk sebagai admin</h2>
          <p>Akses pengelolaan dokumen dan pemrosesan knowledge base.</p>
          {health && !health.admin_configured && (
            <div className="alert warning">
              Akun admin belum dibuat. Jalankan setup akun sesuai README terlebih dahulu.
            </div>
          )}
          <form onSubmit={login}>
            <label>
              Nama pengguna
              <input
                autoComplete="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                required
                maxLength={80}
              />
            </label>
            <label>
              Password
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                maxLength={256}
              />
            </label>
            <button className="button primary" disabled={busy}>
              {busy ? 'Memeriksa...' : 'Masuk'}
              <Icon name="arrow" size={17} />
            </button>
          </form>
        </div>
      ) : (
        <>
          <div className="stats">
            <div>
              <span>Dokumen tersimpan</span>
              <strong>{docs.length.toString().padStart(2, '0')}</strong>
              <Icon name="file" size={26} />
            </div>
            <div>
              <span>Siap digunakan</span>
              <strong>{ready.toString().padStart(2, '0')}</strong>
              <Icon name="check" size={26} />
            </div>
            <div>
              <span>Sedang diproses</span>
              <strong>{processing.toString().padStart(2, '0')}</strong>
              <Icon name="upload" size={26} />
            </div>
          </div>
          {!health?.ai_ready && (
            <div className="alert warning">
              <Icon name="info" />
              Relay AI belum terhubung. Konfigurasi layanan diperlukan sebelum dokumen dapat
              diproses.
            </div>
          )}
          <div className="admin-grid">
            <section className="panel upload-panel">
              <div className="panel-heading">
                <h2>Tambahkan dokumen</h2>
                <span>PDF · Maks. 100 MB</span>
              </div>
              <form onSubmit={upload}>
                <label
                  className="dropzone"
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={(event) => {
                    event.preventDefault();
                    choose(event.dataTransfer.files[0] ?? null);
                  }}
                >
                  <span className="upload-icon">
                    <Icon name="upload" size={25} />
                  </span>
                  <strong>{file ? file.name : 'Pilih atau letakkan PDF di sini'}</strong>
                  <span>
                    {file
                      ? (file.size / 1024 / 1024).toFixed(1) + ' MB'
                      : 'Mendukung dokumen teks dan hasil scan'}
                  </span>
                  <input
                    ref={fileInput}
                    type="file"
                    accept="application/pdf,.pdf"
                    onChange={(event) => choose(event.target.files?.[0] ?? null)}
                    disabled={busy}
                  />
                </label>
                <label>
                  Nama dokumen
                  <input
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    placeholder="Nama yang akan tampil pada referensi"
                    maxLength={180}
                    required
                  />
                </label>
                <button className="button primary" disabled={busy || !file || !health?.ai_ready}>
                  <Icon name="upload" size={17} />
                  {busy ? 'Memproses permintaan...' : 'Upload dan proses'}
                </button>
              </form>
            </section>
            <aside className="panel ocr-panel">
              <div className="notice-icon">
                <Icon name="info" size={22} />
              </div>
              <span className="eyebrow">KUALITAS KNOWLEDGE BASE</span>
              <h2>Perhatian terhadap akurasi OCR</h2>
              <p>
                Ekstraksi dokumen scan dapat menghasilkan kesalahan, terutama pada angka, tabel, dan
                kata yang memengaruhi makna ketentuan. Pemeriksaan hasil OCR tetap diperlukan
                sebelum penggunaan operasional.
              </p>
              <p>
                Pemeriksaan lokal berjalan tanpa menunggu AI. Halaman yang meragukan dan tabel
                dibaca langsung dari gambar asli oleh GPT-4.1 mini. Hubungan baris, kolom, dan sel
                gabungan ikut diperiksa. GPT-5.6 Sol membaca bagian yang belum jelas; hasil yang
                tetap meragukan masuk review admin. Bantuan AI berbayar. Model chatbot tetap GPT-4o
                mini.
              </p>
              <div className="development-note">
                <span>REVIEW OLEH ADMIN</span>
                <p>
                  Gunakan “Review dan koreksi” pada dokumen gagal. Gambar asli dan teks ditampilkan
                  per halaman. Hanya halaman yang ditandai perlu review yang wajib dikonfirmasi;
                  tersedia juga pilihan meninjau seluruh dokumen.
                </p>
                <small>Penyiapan review lokal tidak menggunakan OCR AI berbayar.</small>
              </div>
            </aside>
          </div>
          {reviewing && (
            <DocumentReview
              key={reviewing.id}
              doc={reviewing}
              onClose={() => setReviewing(null)}
              onIndexed={() => {
                setReviewing(null);
                refresh();
                setNotice('Hasil review masuk antrean pembuatan indeks.');
              }}
            />
          )}
          <section className="panel documents-panel">
            <div className="panel-heading">
              <h2>Dokumen knowledge base</h2>
              <span>Disimpan persisten pada komputer ini</span>
            </div>
            {!docs.length ? (
              <div className="documents-empty">
                <Icon name="book" size={34} />
                <h3>Belum ada dokumen</h3>
                <p>Upload PDF pertama untuk menambahkan pengetahuan SIRA.</p>
              </div>
            ) : (
              <div className="documents-list">
                {docs.map((doc) => (
                  <article className="document" key={doc.id}>
                    <div className="document-icon">
                      <Icon name="file" size={24} />
                    </div>
                    <div className="document-body">
                      <div className="document-top">
                        <h3>{doc.title}</h3>
                        <span className={'status-tag ' + doc.status}>
                          {doc.status === 'ready'
                            ? 'Siap digunakan'
                            : doc.status === 'failed'
                              ? 'Gagal diproses'
                              : doc.status === 'review'
                                ? doc.review_source
                                  ? 'Siap · review opsional'
                                  : 'Menunggu review'
                                : 'Sedang diproses'}
                        </span>
                      </div>
                      <p className="document-meta">
                        {doc.filename} · {(doc.size / 1024 / 1024).toFixed(1)} MB
                        {doc.page_count ? ' · ' + doc.page_count + ' halaman' : ''}
                      </p>
                      {!!doc.available && doc.pending_version && (
                        <p className="version-note">Versi sebelumnya tetap tersedia untuk chat.</p>
                      )}
                      {doc.status === 'processing' && (
                        <div className="progress-wrap">
                          <progress value={doc.progress} max={100} />
                          <span>
                            {doc.stage} · {doc.progress}%
                          </span>
                        </div>
                      )}
                      {doc.error && <p className="document-error">{doc.error}</p>}
                      {doc.verification && (
                        <div className="verification-note">
                          <p>
                            <strong>
                              {doc.verification.accepted_pages} halaman pada versi aktif siap
                              digunakan.
                            </strong>{' '}
                            {doc.verification.recommended_parts
                              ? `${doc.verification.recommended_parts} bagian disarankan diperiksa; review bersifat opsional.`
                              : 'Tidak ada bagian yang ditandai untuk review tambahan.'}
                          </p>
                          <p className="document-meta">
                            {doc.verification.local_score === null
                              ? 'Skor OCR lokal tidak tersedia untuk versi ini.'
                              : `Indikator OCR lokal: ${doc.verification.local_score}/100 · rata-rata ${doc.verification.scored_pages} halaman dengan bukti tersimpan.`}{' '}
                            Skor ini bukan persentase kebenaran dokumen. Detail tersedia di Review
                            dan koreksi.
                          </p>
                        </div>
                      )}
                      {doc.warning && (
                        <details className="ocr-details">
                          <summary>Peringatan kualitas ekstraksi</summary>
                          <p>{doc.warning}</p>
                        </details>
                      )}
                      {doc.ocr_mode === 'ai' && (
                        <p className="document-meta">
                          OCR lokal → GPT-4.1 mini → GPT-5.6 Sol untuk bagian meragukan
                        </p>
                      )}
                      {editing === doc.id ? (
                        <form
                          className="edit-form"
                          onSubmit={(event) => {
                            event.preventDefault();
                            action(async () => {
                              await api('/admin/documents/' + doc.id, {
                                method: 'PATCH',
                                body: JSON.stringify({ title: editTitle }),
                              });
                              setEditing('');
                            }, 'Nama dokumen diperbarui.');
                          }}
                        >
                          <input
                            aria-label="Nama dokumen baru"
                            value={editTitle}
                            onChange={(event) => setEditTitle(event.target.value)}
                            required
                            maxLength={180}
                          />
                          <button className="button secondary compact" disabled={busy}>
                            Simpan
                          </button>
                          <button
                            className="text-button"
                            type="button"
                            onClick={() => setEditing('')}
                          >
                            Batal
                          </button>
                        </form>
                      ) : (
                        <div className="document-actions">
                          <button
                            className="text-button"
                            disabled={busy}
                            onClick={() => {
                              setEditing(doc.id);
                              setEditTitle(doc.title);
                            }}
                          >
                            Ubah nama
                          </button>
                          <label
                            className={
                              'text-button file-action ' +
                              (busy || doc.status === 'processing' ? 'disabled' : '')
                            }
                          >
                            Ganti file
                            <input
                              type="file"
                              accept="application/pdf,.pdf"
                              disabled={busy || doc.status === 'processing'}
                              onChange={(event) => {
                                replace(doc, event.target.files?.[0] ?? null);
                                event.target.value = '';
                              }}
                            />
                          </label>
                          {(doc.status === 'failed' ||
                            doc.status === 'review' ||
                            doc.status === 'ready') && (
                            <>
                              {doc.status === 'failed' && (
                                <button
                                  className="text-button"
                                  disabled={busy}
                                  onClick={() =>
                                    action(
                                      () =>
                                        api('/admin/documents/' + doc.id + '/retry', {
                                          method: 'POST',
                                        }),
                                      'Dokumen masuk antrean proses ulang.',
                                    )
                                  }
                                >
                                  Proses ulang
                                </button>
                              )}
                              <button
                                className="text-button"
                                disabled={busy || !health?.ai_ready}
                                title="Periksa scan dengan GPT-4.1 mini dan fallback Sol pada potongan meragukan; API berbayar"
                                onClick={() =>
                                  action(
                                    () =>
                                      api('/admin/documents/' + doc.id + '/read-ai', {
                                        method: 'POST',
                                      }),
                                    'Dokumen masuk antrean pembacaan AI. Hasil tetap diperiksa sebelum diaktifkan.',
                                  )
                                }
                              >
                                {doc.status === 'ready' ? 'Baca ulang dengan AI' : 'Baca dengan AI'}
                              </button>
                            </>
                          )}
                          {(doc.status === 'failed' ||
                            doc.status === 'ready' ||
                            doc.status === 'review' ||
                            (doc.status === 'processing' && doc.ocr_mode === 'review')) && (
                            <button
                              className="text-button"
                              disabled={busy}
                              onClick={() =>
                                action(async () => {
                                  await api('/admin/documents/' + doc.id + '/review', {
                                    method: 'POST',
                                  });
                                  setReviewing(doc);
                                }, 'Review dokumen dibuka. Koreksi disimpan sebagai draft; versi aktif tetap tersedia untuk chat.')
                              }
                            >
                              Review dan koreksi
                            </button>
                          )}
                          <button
                            className="text-button danger"
                            disabled={busy}
                            onClick={() => setDeleting(doc)}
                          >
                            <Icon name="trash" size={14} />
                            Hapus
                          </button>
                        </div>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
          <p className="page-footnote">
            Akun: {user} · Dokumen tetap tersimpan setelah aplikasi ditutup.
          </p>
        </>
      )}
      {deleting && (
        <div className="modal-backdrop">
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="delete-title">
            <span className="notice-icon">
              <Icon name="trash" size={22} />
            </span>
            <h2 id="delete-title">Hapus dokumen?</h2>
            <p>
              “{deleting.title}” akan dikeluarkan dari knowledge base dan tidak digunakan lagi untuk
              menjawab pertanyaan.
            </p>
            <div className="modal-actions">
              <button
                className="button secondary"
                disabled={busy}
                onClick={() => setDeleting(null)}
              >
                Batal
              </button>
              <button
                className="button danger-button"
                disabled={busy}
                onClick={() =>
                  action(async () => {
                    await api('/admin/documents/' + deleting.id, { method: 'DELETE' });
                    setDeleting(null);
                  }, 'Dokumen telah dikeluarkan dari knowledge base.')
                }
              >
                Hapus dokumen
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

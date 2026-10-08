let csrf = '';
export function setCsrf(value: string) {
  csrf = value;
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData))
    headers.set('Content-Type', 'application/json');
  if (csrf) headers.set('X-CSRF-Token', csrf);
  const response = await fetch('/api' + path, { ...options, headers, credentials: 'same-origin' });
  if (!response.ok) {
    const result = await response
      .json()
      .catch(() => ({ detail: 'Layanan belum dapat dihubungi.' }));
    throw new Error(
      typeof result.detail === 'string'
        ? result.detail
        : 'Permintaan belum berhasil. Silakan coba kembali.',
    );
  }
  return response.json();
}

export type Health = {
  ai_ready: boolean;
  knowledge_documents: number;
  kb_revision: number;
  admin_configured: boolean;
};
export type Source = { id: string; title: string; page: number; heading: string };
export type Doc = {
  id: string;
  title: string;
  filename: string;
  status: string;
  stage: string;
  progress: number;
  page_count: number;
  warning: string;
  error: string;
  size: number;
  available: number;
  pending_version: string | null;
};

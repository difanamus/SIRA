import { prepare } from './policy';

interface Env {
  OPENAI_API_KEY: string;
  RELAY_TOKEN_HASH: string;
  RELAY_ENABLED: string;
  RELAY_EXPIRES_AT: string;
  MAX_REQUESTS: string;
  MAX_TOKEN_UNITS: string;
  REQUESTS_PER_MINUTE: string;
  QUOTA: DurableObjectNamespace;
}
type Counter = { requests: number; units: number; minute: number; minuteRequests: number };
const json = (detail: string, status: number) =>
  Response.json({ detail }, { status, headers: { 'Cache-Control': 'no-store' } });

function positive(value: string, fallback: number) {
  const number = Number(value);
  return Number.isSafeInteger(number) && number > 0 ? number : fallback;
}

export class Quota {
  constructor(
    private state: DurableObjectState,
    private env: Env,
  ) {}

  async fetch(request: Request): Promise<Response> {
    const { units } = (await request.json()) as { units: number };
    if (!Number.isSafeInteger(units) || units < 1 || units > 200000)
      return json('Reservasi tidak valid.', 400);
    return this.state.storage.transaction(async (txn) => {
      const minute = Math.floor(Date.now() / 60000);
      const counter = (await txn.get<Counter>('usage')) ?? {
        requests: 0,
        units: 0,
        minute,
        minuteRequests: 0,
      };
      if (counter.minute !== minute) {
        counter.minute = minute;
        counter.minuteRequests = 0;
      }
      if (
        counter.requests >= positive(this.env.MAX_REQUESTS, 1000) ||
        counter.units + units > positive(this.env.MAX_TOKEN_UNITS, 2000000) ||
        counter.minuteRequests >= positive(this.env.REQUESTS_PER_MINUTE, 30)
      ) {
        return json('Batas penggunaan layanan AI tercapai.', 429);
      }
      counter.requests++;
      counter.units += units;
      counter.minuteRequests++;
      await txn.put('usage', counter);
      return Response.json({ ok: true });
    });
  }
}

async function authorised(request: Request, expected: string): Promise<boolean> {
  if (!/^[a-f0-9]{64}$/.test(expected ?? '')) return false;
  const header = request.headers.get('Authorization') ?? '';
  if (!header.startsWith('Bearer ') || header.length > 200) return false;
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(header.slice(7)));
  const actual = Array.from(new Uint8Array(bytes), (value) =>
    value.toString(16).padStart(2, '0'),
  ).join('');
  let difference = 0;
  for (let i = 0; i < 64; i++) difference |= actual.charCodeAt(i) ^ expected.charCodeAt(i);
  return difference === 0;
}

async function readBody(request: Request) {
  const maximum = 8 * 1024 * 1024;
  if (Number(request.headers.get('content-length') ?? 0) > maximum)
    throw new Error('Payload terlalu besar.');
  const reader = request.body?.getReader();
  if (!reader) throw new Error('Body diperlukan.');
  const chunks: Uint8Array[] = [];
  let length = 0;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    length += value.length;
    if (length > maximum) {
      await reader.cancel();
      throw new Error('Payload terlalu besar.');
    }
    chunks.push(value);
  }
  const buffer = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    buffer.set(chunk, offset);
    offset += chunk.length;
  }
  return JSON.parse(new TextDecoder().decode(buffer));
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (!['/embeddings', '/answer', '/vision'].includes(url.pathname))
      return json('Tidak ditemukan.', 404);
    if (request.method !== 'POST') return json('Metode tidak diizinkan.', 405);
    if (!(await authorised(request, env.RELAY_TOKEN_HASH))) return json('Akses ditolak.', 401);
    const expiry = Date.parse(env.RELAY_EXPIRES_AT);
    if (env.RELAY_ENABLED !== 'true' || !Number.isFinite(expiry) || Date.now() >= expiry)
      return json('Akses pengujian tidak aktif atau sudah berakhir.', 403);
    if (!env.OPENAI_API_KEY) return json('Layanan belum dikonfigurasi.', 503);
    if (!request.headers.get('content-type')?.includes('application/json'))
      return json('JSON diperlukan.', 415);
    let prepared;
    try {
      prepared = prepare(url.pathname, await readBody(request));
    } catch {
      return json('Payload tidak valid, terlalu besar, atau operasi tidak diizinkan.', 400);
    }
    const quota = env.QUOTA.get(env.QUOTA.idFromName('testing-budget-v1'));
    const reservation = await quota.fetch('https://quota/reserve', {
      method: 'POST',
      body: JSON.stringify({ units: prepared.units }),
    });
    if (!reservation.ok) return json('Batas penggunaan layanan AI tercapai.', 429);
    try {
      const upstream = await fetch('https://api.openai.com/v1/' + prepared.upstream, {
        method: 'POST',
        redirect: 'manual',
        signal: AbortSignal.timeout(80000),
        headers: {
          Authorization: 'Bearer ' + env.OPENAI_API_KEY,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(prepared.body),
      });
      if (!upstream.ok) {
        await upstream.body?.cancel();
        return json(
          upstream.status === 429
            ? 'Layanan AI mencapai batas penggunaan.'
            : 'Layanan AI belum tersedia.',
          upstream.status === 429 ? 429 : 502,
        );
      }
      // Forward the stream directly: no text()/json() on a streaming answer.
      return new Response(upstream.body, {
        status: 200,
        headers: {
          'Content-Type': prepared.streaming ? 'text/event-stream' : 'application/json',
          'Cache-Control': 'no-store',
          'X-Content-Type-Options': 'nosniff',
        },
      });
    } catch (error) {
      console.warn('upstream_failed', error instanceof Error ? error.name : 'unknown');
      return json('Koneksi layanan AI terputus atau melewati batas waktu.', 504);
    }
  },
};

import { prepare } from './policy';
import { actualCost, reserveCost } from './cost';

interface Env {
  OPENAI_API_KEY: string;
  RELAY_TOKEN_HASH: string;
  INSTALLATION_ACCESS_ENABLED?: string;
  INSTALLATION_TOKEN?: string;
  RELAY_ENABLED: string;
  RELAY_EXPIRES_AT: string;
  MAX_REQUESTS: string;
  MAX_TOKEN_UNITS: string;
  REQUESTS_PER_MINUTE: string;
  TOTAL_QUOTA_ENABLED?: string;
  RUN_BUDGET_ID?: string;
  RUN_BUDGET_MICRO_USD?: string;
  QUOTA: DurableObjectNamespace;
}
type Counter = { requests: number; units: number; minute: number; minuteRequests: number };
const json = (detail: string, status: number, code?: string) =>
  Response.json(
    { detail, ...(code ? { code } : {}) },
    { status, headers: { 'Cache-Control': 'no-store' } },
  );

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
    if (new URL(request.url).pathname === '/settle') {
      const { id, actual } = (await request.json()) as { id: string; actual: number };
      if (typeof id !== 'string' || !Number.isSafeInteger(actual) || actual < 0)
        return json('Biaya tidak valid.', 400);
      return this.state.storage.transaction(async (txn) => {
        const lease = await txn.get<{ key: string; amount: number }>('cost-lease:' + id);
        if (!lease) return json('Reservasi tidak ditemukan.', 409);
        // Never refund an invalid/unexpected usage amount. Keep the conservative hold.
        if (actual > lease.amount) return json('Biaya melebihi reservasi.', 409);
        const spent = (await txn.get<number>(lease.key)) ?? 0;
        await txn.put(lease.key, spent - lease.amount + actual);
        await txn.delete('cost-lease:' + id);
        return Response.json({ ok: true });
      });
    }
    const { units, limits, budget, cost } = (await request.json()) as {
      units: number;
      limits?: { requests: number; units: number; minute: number; totalEnabled?: boolean };
      budget?: { id: string; limit: number };
      cost?: number;
    };
    if (!Number.isSafeInteger(units) || units < 1 || units > 200000)
      return json('Reservasi tidak valid.', 400);
    if (limits && (
      [limits.requests, limits.units, limits.minute].some((value) => !Number.isSafeInteger(value) || value < 1) ||
      (limits.totalEnabled !== undefined && typeof limits.totalEnabled !== 'boolean')
    ))
      return json('Batas tidak valid.', 400);
    if (
      budget &&
      (!/^[A-Za-z0-9_-]{1,64}$/.test(budget.id) ||
        !Number.isSafeInteger(budget.limit) ||
        budget.limit < 1 ||
        !Number.isSafeInteger(cost) ||
        cost! < 1)
    )
      return json('Anggaran tidak valid.', 400);
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
        limits?.totalEnabled !== false && (
          counter.requests >= (limits?.requests ?? positive(this.env.MAX_REQUESTS, 1000)) ||
          counter.units + units > (limits?.units ?? positive(this.env.MAX_TOKEN_UNITS, 2000000))
        )
      ) {
        return json('Kuota total relay tidak mencukupi untuk permintaan ini.', 429, 'relay_budget');
      }
      if (counter.minuteRequests >= (limits?.minute ?? positive(this.env.REQUESTS_PER_MINUTE, 30)))
        return json('Batas permintaan per menit tercapai.', 429, 'relay_rate');
      let reservationId: string | undefined;
      if (budget) {
        const key = 'run-spend:' + budget.id;
        const spent = (await txn.get<number>(key)) ?? 0;
        if (spent + cost! > budget.limit)
          return json('Batas biaya uji tercapai.', 429, 'relay_cost');
        reservationId = crypto.randomUUID();
        await txn.put(key, spent + cost!);
        await txn.put('cost-lease:' + reservationId, { key, amount: cost! });
      }
      counter.requests++;
      counter.units += units;
      counter.minuteRequests++;
      await txn.put('usage', counter);
      return Response.json({ ok: true, reservationId });
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

async function installationHash(env: Env): Promise<string | null> {
  if (env.INSTALLATION_ACCESS_ENABLED !== 'true' ||
      !/^[A-Za-z0-9_-]{40,100}$/.test(env.INSTALLATION_TOKEN ?? '')) return null;
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(env.INSTALLATION_TOKEN));
  return Array.from(new Uint8Array(bytes), (value) => value.toString(16).padStart(2, '0')).join('');
}

function active(env: Env): boolean {
  const expiry = Date.parse(env.RELAY_EXPIRES_AT);
  return env.RELAY_ENABLED === 'true' && Number.isFinite(expiry) && Date.now() < expiry;
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
    // This is an explicitly public, time-limited demo credential, not the owner's
    // private relay token or OpenAI key. Anonymous installers cannot be identified
    // as judges. Disabling installation access also revokes this demo credential.
    if (url.pathname === '/installation') {
      if (request.method !== 'GET') return json('Metode tidak diizinkan.', 405);
      if (!active(env) || !(await installationHash(env)))
        return json('Instalasi otomatis tidak aktif atau masa akses sudah berakhir.', 403);
      if (!env.OPENAI_API_KEY) return json('Layanan belum dikonfigurasi.', 503);
      return Response.json({
        relay_url: url.origin,
        relay_token: env.INSTALLATION_TOKEN,
        expires_at: env.RELAY_EXPIRES_AT,
        access: 'public-demo',
      }, { headers: { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' } });
    }
    if (!['/embeddings', '/answer', '/vision', '/vision-fragment'].includes(url.pathname))
      return json('Tidak ditemukan.', 404);
    if (request.method !== 'POST') return json('Metode tidak diizinkan.', 405);
    const demoHash = await installationHash(env);
    if (!(await authorised(request, env.RELAY_TOKEN_HASH)) &&
        !(demoHash && await authorised(request, demoHash))) return json('Akses ditolak.', 401);
    if (!active(env))
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
    const cost = reserveCost(prepared);
    // Owner-controlled switch: remove cumulative test caps without clearing history
    // or allowing clients to change quota policy. Minute throttling stays active.
    const totalEnabled = env.TOTAL_QUOTA_ENABLED !== 'false';
    const budgetConfigured = totalEnabled && (
      env.RUN_BUDGET_ID !== undefined || env.RUN_BUDGET_MICRO_USD !== undefined
    );
    const budget = budgetConfigured
      ? { id: env.RUN_BUDGET_ID ?? '', limit: Number(env.RUN_BUDGET_MICRO_USD) }
      : undefined;
    if (
      budget &&
      (!/^[A-Za-z0-9_-]{1,64}$/.test(budget.id) ||
        !Number.isSafeInteger(budget.limit) ||
        budget.limit < 1)
    )
      return json('Anggaran uji belum dikonfigurasi dengan benar.', 503);
    const reservation = await quota.fetch('https://quota/reserve', {
      method: 'POST',
      // Limits come only from this authenticated Worker's current bindings,
      // never from a caller's payload or a cached constructor binding.
      body: JSON.stringify({
        units: prepared.units,
        cost,
        budget,
        limits: {
          totalEnabled,
          requests: positive(env.MAX_REQUESTS, 1000),
          units: positive(env.MAX_TOKEN_UNITS, 2000000),
          minute: positive(env.REQUESTS_PER_MINUTE, 30),
        },
      }),
    });
    if (!reservation.ok) {
      const limit = (await reservation.json()) as { code?: string };
      return json('Batas penggunaan layanan AI tercapai.', 429, limit.code);
    }
    const { reservationId } = (await reservation.json()) as { reservationId?: string };
    const settle = async (actual: number) => {
      if (reservationId)
        await quota.fetch('https://quota/settle', {
          method: 'POST',
          body: JSON.stringify({ id: reservationId, actual }),
        });
    };
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
          upstream.status === 429 ? 'upstream_rate' : undefined,
        );
      }
      if (reservationId && !prepared.streaming) {
        const packet = await upstream.json();
        const actual = actualCost(prepared, packet);
        // Unknown billing/transport failures retain their full reservation.
        if (actual !== null) await settle(actual);
        return Response.json(packet, {
          headers: { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' },
        });
      }
      if (prepared.streaming) await settle(cost); // Streaming stays conservatively charged.
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

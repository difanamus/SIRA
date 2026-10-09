import type { Prepared } from './policy';

// Micro-USD rates per token, checked against the model price pages on 2026-10-08.
const rates: Record<string, [number, number, number]> = {
  'gpt-4o-mini': [0.15, 0.075, 0.6],
  'gpt-4.1-mini': [0.4, 0.1, 1.6],
  'gpt-5.6-sol': [4, 0.4, 20],
  'text-embedding-3-small': [0.02, 0.02, 0],
};

export function reserveCost(prepared: Prepared): number {
  const model = String(prepared.body.model);
  // Vision inputs are patch/tile capped by these fixed models. These allowances
  // exceed the bounded two-image mini / one-image Sol inputs and output limits.
  if (model === 'gpt-4.1-mini' && !prepared.streaming)
    return Number(prepared.body.max_completion_tokens) > 6000 ? 30000 : 15000;
  if (model === 'gpt-5.6-sol')
    return Number(prepared.body.max_completion_tokens) > 4000 ? 300000 : 150000;
  const [input, , output] = rates[model];
  const bytes = new TextEncoder().encode(JSON.stringify(prepared.body)).length;
  return Math.ceil(
    (bytes + 512) * input + Number(prepared.body.max_completion_tokens ?? 0) * output,
  );
}

export function actualCost(prepared: Prepared, packet: unknown): number | null {
  const usage = (
    packet as {
      usage?: {
        prompt_tokens?: number;
        completion_tokens?: number;
        prompt_tokens_details?: { cached_tokens?: number };
      };
    }
  )?.usage;
  if (!usage || !Number.isSafeInteger(usage.prompt_tokens) || (usage.prompt_tokens ?? -1) < 0)
    return null;
  const prompt = usage.prompt_tokens!;
  const completion = usage.completion_tokens ?? 0;
  const cached = usage.prompt_tokens_details?.cached_tokens ?? 0;
  if (
    !Number.isSafeInteger(completion) ||
    completion < 0 ||
    !Number.isSafeInteger(cached) ||
    cached < 0 ||
    cached > prompt
  )
    return null;
  const [input, cache, output] = rates[String(prepared.body.model)];
  // completion_tokens already includes reasoning tokens.
  return Math.ceil((prompt - cached) * input + cached * cache + completion * output);
}

import test from 'node:test';
import assert from 'node:assert/strict';
import { actualCost, reserveCost } from '../src/cost';
import { prepare } from '../src/policy';

test('Luna chat reserves text and cache-write costs while vision keeps its image allowance', () => {
  const chat = prepare('/answer', {
    question: 'Kapan kelulusan?',
    history: [],
    sources: [{ id: 'S1', title: 'Jadwal', page: 12, text: '23–26 November 2026.' }],
  });
  const bytes = new TextEncoder().encode(JSON.stringify(chat.body)).length;
  assert.equal(reserveCost(chat), Math.ceil((bytes + 512) * 0.125 + 1800 * 0.5));
  assert.equal(
    actualCost(chat, {
      usage: { prompt_tokens: 1000, completion_tokens: 100 },
    }),
    150,
  );
  assert.equal(
    actualCost(chat, {
      usage: {
        prompt_tokens: 1000,
        completion_tokens: 100,
        prompt_tokens_details: { cached_tokens: 400, cache_write_tokens: 200 },
      },
    }),
    119,
  );
  assert.equal(
    actualCost(chat, {
      usage: {
        prompt_tokens: 1000,
        prompt_tokens_details: { cached_tokens: 800, cache_write_tokens: 201 },
      },
    }),
    null,
  );
  const image = 'data:image/jpeg;base64,YWJj';
  assert.equal(reserveCost(prepare('/vision', { image })), 15000);
  assert.equal(reserveCost(prepare('/vision', { image, layout: true })), 30000);
});

test('cost includes cached input and reasoning once, rounded upwards to micro-USD', () => {
  const image = 'data:image/jpeg;base64,YWJj';
  const sol = prepare('/vision-fragment', { image });
  assert.equal(reserveCost(sol), 150000);
  assert.equal(
    actualCost(sol, {
      usage: {
        prompt_tokens: 1195,
        completion_tokens: 175,
        completion_tokens_details: { reasoning_tokens: 43 },
      },
    }),
    8280,
  );
  assert.equal(
    actualCost(sol, {
      usage: {
        prompt_tokens: 100,
        completion_tokens: 10,
        prompt_tokens_details: { cached_tokens: 50 },
      },
    }),
    420,
  );
  assert.equal(
    actualCost(sol, { usage: { prompt_tokens: 10, prompt_tokens_details: { cached_tokens: 11 } } }),
    null,
  );
  assert.equal(actualCost(sol, {}), null);
});

test('rewrite is reserved by size, not with the larger vision allowance', () => {
  const rewrite = prepare('/rewrite', { question: 'apa aja saratnya?', history: [], documents: ['SBP'] });
  const reserved = reserveCost(rewrite);
  assert.ok(reserved > 0 && reserved < 2000);
});

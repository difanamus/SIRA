import test from 'node:test';
import assert from 'node:assert/strict';
import { actualCost, reserveCost } from '../src/cost';
import { prepare } from '../src/policy';

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

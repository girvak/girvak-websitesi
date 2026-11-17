import test from 'node:test';
import assert from 'node:assert/strict';
import { PALETTES, next, paletteFor } from '../src/scripts/selection.js';

test('default pages rotate blue, coral and grey with white text', () => {
  assert.equal(PALETTES.default.length, 3);
  assert.deepEqual(PALETTES.default.map(([bg]) => bg), ['var(--turquoise)', 'var(--coral)', 'var(--ink-700)']);
  assert.ok(PALETTES.default.every(([, fg]) => fg === '#fff'));
});

test('fellow, challenger and fellow-program pages rotate yellow and red', () => {
  for (const cls of ['fl', 'ca', 'fp']) assert.equal(paletteFor(['hm', cls]), PALETTES.fellow);
  assert.equal(paletteFor(['hm', 'ap', 'al']), PALETTES.default);
  assert.equal(paletteFor(['hm', 'ab']), PALETTES.default);
});

test('the index wraps around', () => {
  assert.equal(next(0, 3), 1);
  assert.equal(next(2, 3), 0);
  assert.equal(next(1, 2), 0);
});

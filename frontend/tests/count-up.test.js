import test from 'node:test';
import assert from 'node:assert/strict';
import { easeOut, formatCount } from '../src/scripts/count-up.js';

test('a counter prints its prefix, value to the places given, and suffix', () => {
  assert.equal(formatCount(12, 0), '12');
  assert.equal(formatCount(45, 0, '%'), '%45');
  assert.equal(formatCount(8, 0, '', ' yrs'), '8 yrs');
  assert.equal(formatCount(1.25, 1), '1.3');
  // Thousands separators only where the editor wrote them: a year stays a year.
  assert.equal(formatCount(1076, 0, '', '', true), '1,076');
  assert.equal(formatCount(1340000, 0, '', ' TL', true), '1,340,000 TL');
  assert.equal(formatCount(2016, 0, 'Since '), 'Since 2016');
});

test('the easing runs from 0 to 1 and never leaves that range', () => {
  assert.equal(easeOut(0), 0);
  assert.equal(easeOut(1), 1);
  assert.equal(easeOut(-3), 0);
  assert.equal(easeOut(9), 1);
  assert.ok(easeOut(0.5) > 0.5, 'it is fast at the start');
});

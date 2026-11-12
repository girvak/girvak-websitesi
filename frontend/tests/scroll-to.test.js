import test from 'node:test';
import assert from 'node:assert/strict';
import { GAP, targetY } from '../src/scripts/scroll-to.js';

test('the heading lands just under the nav, whatever its height', () => {
  // heading 900px down the viewport, page at 0, nav 134px tall
  assert.equal(targetY(900, 0, 134, 5000), 900 - 134 - GAP);
  // same heading with a shorter (mobile) nav
  assert.equal(targetY(900, 0, 90, 5000), 900 - 90 - GAP);
});

test('works from a scrolled position and above the viewport', () => {
  assert.equal(targetY(300, 1000, 134, 5000), 1300 - 134 - GAP);
  assert.equal(targetY(-200, 1000, 134, 5000), 800 - 134 - GAP);
});

test('never scrolls past the top or the bottom of the page', () => {
  assert.equal(targetY(50, 0, 134, 5000), 0);
  assert.equal(targetY(4000, 0, 134, 1500), 1500);
  assert.equal(targetY(100, 0, 0, -10), 0);
});

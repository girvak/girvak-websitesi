import test from 'node:test';
import assert from 'node:assert/strict';
import { entrySide, flipFor } from '../src/scripts/card-direction.js';

const card = { left: 100, top: 100, width: 200, height: 300 };

test('the entry side is the nearest edge', () => {
  assert.equal(entrySide(card, 101, 250), 'left');
  assert.equal(entrySide(card, 299, 250), 'right');
  assert.equal(entrySide(card, 200, 101), 'top');
  assert.equal(entrySide(card, 200, 399), 'bottom');
});

test('a tall card is measured by its own proportions, not by pixels', () => {
  // 40px in from the left of a 200-wide card is 20%; 40px down a 300-tall one is 13%.
  assert.equal(entrySide(card, 140, 140), 'top');
});

test('each side turns its own edge away', () => {
  assert.equal(flipFor('left'), 'rotateY(-180deg)');
  assert.equal(flipFor('right'), 'rotateY(180deg)');
  assert.equal(flipFor('top'), 'rotateX(180deg)');
  assert.equal(flipFor('bottom'), 'rotateX(-180deg)');
});

test('a Y-only card turns left or right even when entered from top or bottom', () => {
  assert.equal(flipFor('top', 'y', true), 'rotateY(180deg)');
  assert.equal(flipFor('bottom', 'y', false), 'rotateY(-180deg)');
  assert.equal(flipFor('left', 'y'), 'rotateY(-180deg)');
});

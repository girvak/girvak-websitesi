import test from 'node:test';
import assert from 'node:assert/strict';
import { URGENT_DAYS, arrange, daysLeft, formatDeadline, popupCalls, rate, todayIn } from '../src/scripts/open-calls.js';

const call = (title, deadline = null, popup = false) => ({ title, text: '', href: '#', deadline, popup });

test('today is the date in İstanbul, not UTC', () => {
  // 22:30 UTC on 13 October is already 14 October in İstanbul (UTC+3).
  assert.equal(todayIn(new Date('2026-10-13T22:30:00Z')), '2026-10-14');
  assert.equal(todayIn(new Date('2026-10-13T20:30:00Z')), '2026-10-13');
});

test('daysLeft counts whole days and goes negative after the deadline', () => {
  assert.equal(daysLeft('2026-10-20', '2026-10-13'), 7);
  assert.equal(daysLeft('2026-10-13', '2026-10-13'), 0);
  assert.equal(daysLeft('2026-10-12', '2026-10-13'), -1);
  // across the end of daylight saving in Europe
  assert.equal(daysLeft('2026-11-02', '2026-10-20'), 13);
});

test('the deadline day is still open, and urgent; the day after is closed', () => {
  assert.equal(rate(call('a', '2026-10-13'), '2026-10-13').state, 'urgent');
  assert.equal(rate(call('a', '2026-10-12'), '2026-10-13').state, 'closed');
});

test(`a call is urgent with ${URGENT_DAYS} days or fewer left`, () => {
  assert.equal(rate(call('a', '2026-10-20'), '2026-10-13').state, 'urgent');
  assert.equal(rate(call('a', '2026-10-21'), '2026-10-13').state, 'open');
});

test('a call without a deadline is always open', () => {
  assert.equal(rate(call('Fellow'), '2026-10-13').state, 'always');
});

test('always-open first, then nearest deadline, then most recently closed', () => {
  const order = arrange(
    [
      call('closed long ago', '2026-03-01'),
      call('later', '2026-12-01'),
      call('fellow'),
      call('sooner', '2026-10-15'),
      call('just closed', '2026-10-01'),
    ],
    '2026-10-13',
  ).map((c) => c.title);

  assert.deepEqual(order, ['fellow', 'sooner', 'later', 'just closed', 'closed long ago']);
});

test('the year is printed only when it is not this one', () => {
  assert.equal(formatDeadline('2026-09-05', '2026-10-13'), '5 September');
  assert.equal(formatDeadline('2027-01-15', '2026-10-13'), '15 January 2027');
});

test('the popup shows ticked calls that are still open, in page order', () => {
  const shown = popupCalls(
    [
      call('not ticked', '2026-10-20'),
      call('ticked, later', '2026-12-01', true),
      call('ticked, closed', '2026-10-12', true),
      call('ticked, deadline today', '2026-10-13', true),
      call('ticked fellow', null, true),
    ],
    '2026-10-13',
  ).map((c) => c.title);

  assert.deepEqual(shown, ['ticked fellow', 'ticked, deadline today', 'ticked, later']);
});

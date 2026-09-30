import test from 'node:test';
import assert from 'node:assert/strict';
import {
  PAGE_SIZE, visibleCount, hasMore, summary, parseFilters, buildSearch,
} from '../src/scripts/pager.js';

test('the first reveal is 24', () => assert.equal(PAGE_SIZE, 24));

test('visibleCount never exceeds what matched, nor goes negative', () => {
  assert.equal(visibleCount(405, 24), 24);
  assert.equal(visibleCount(10, 24), 10);
  assert.equal(visibleCount(0, 24), 0);
  assert.equal(visibleCount(50, -3), 0);
});

test('hasMore is false exactly when everything is on screen', () => {
  assert.equal(hasMore(405, 24), true);
  assert.equal(hasMore(48, 48), false);
  assert.equal(hasMore(48, 72), false);
  assert.equal(hasMore(0, 24), false);
});

test('summary reads "showing X of Y noun" and is empty with no match', () => {
  assert.equal(summary(405, 24, 'alumni'), 'showing 24 of 405 alumni');
  assert.equal(summary(13, 24, 'fellows'), 'showing 13 of 13 fellows');
  assert.equal(summary(0, 24, 'alumni'), '');
});

test('parseFilters reads repeated values, trims, drops blanks and duplicates', () => {
  const r = parseFilters('?year=25&year=24&year=25&university=Ko%C3%A7%20%C3%9Cniversitesi&department=&q=%20ay%C5%9Fe%20', ['university', 'department', 'year']);
  assert.deepEqual(r.values.year, ['25', '24']);
  assert.deepEqual(r.values.university, ['Koç Üniversitesi']);
  assert.deepEqual(r.values.department, []);
  assert.equal(r.q, 'ayşe');
});

test('parseFilters on an empty query gives empty filters', () => {
  const r = parseFilters('', ['year']);
  assert.deepEqual(r, { q: '', values: { year: [] } });
});

test('buildSearch is "" with no filters, and round-trips through parseFilters', () => {
  const keys = ['university', 'department', 'year'];
  assert.equal(buildSearch('', { university: [], department: [], year: [] }, keys), '');
  const values = { university: ['Koç Üniversitesi'], department: [], year: ['25', '24'] };
  const search = buildSearch('ayşe', values, keys);
  assert.deepEqual(parseFilters(search, keys), { q: 'ayşe', values });
});

test('buildSearch orders parameters by key list, so one view is one URL', () => {
  const keys = ['university', 'year'];
  assert.equal(
    buildSearch('', { year: ['25'], university: ['ODTÜ'] }, keys),
    buildSearch('', { university: ['ODTÜ'], year: ['25'] }, keys),
  );
});

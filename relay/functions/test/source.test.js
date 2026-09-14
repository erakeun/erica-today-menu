"use strict";
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {parse, collect, publicStatus, kstDay, mergeResult} = require('../source');
const fixture = fs.readFileSync(path.resolve(__dirname, '../../../tests/fixtures/hy_square_2026-09-14.html'), 'utf8');
const now = new Date('2026-09-14T01:00:00Z');
const response = (body, status=200, type='text/html') => ({ok: status === 200, status, url: 'https://life.hanyang.ac.kr/theme/pages/home.php', text: async () => body, headers: new Headers({'content-type': type})});

test('actual source: 11 menus and 11 relevant facilities; preserve images/details/date', () => {
  const result = parse(fixture, now);
  assert.equal(result.ok, true);
  assert.equal(result.data.menus.length, 11);
  assert.equal(result.data.facilities.length, 11);
  assert.equal(result.data.menus[0].target_date, '2026-09-14');
  assert.equal(result.data.menus[0].price, 1000);
  assert.ok(result.data.menus[0].image_url);
  assert.ok(result.data.menus[0].description);
  assert.equal('created_at' in result.data.menus[0], false);
});

test('403 and redirects are source errors, exactly one fixed request', async () => {
  for (const status of [403, 302, 503]) {
    let calls = 0;
    const result = await collect(async (url, options) => {
      calls++;
      assert.equal(url, 'https://life.hanyang.ac.kr/theme/pages/home.php');
      assert.equal(options.redirect, 'manual');
      return response('blocked', status);
    }, now);
    assert.equal(calls, 1);
    assert.equal(result.state, 'source_error');
    assert.equal(result.diagnostics.status, status);
  }
});

test('timeout and stream read errors preserve error state', async () => {
  const result = await collect(async () => {throw new DOMException('timeout', 'TimeoutError');}, now);
  assert.equal(result.state, 'source_error');
});

test('login/block HTML and missing arrays are never treated as menus', async () => {
  for (const body of ['<h1>Login</h1>', '<h1>Access denied</h1>', 'const dbMenus = [];']) {
    assert.equal((await collect(async () => response(body), now)).state, 'schema_error');
  }
});

test('empty registered facilities mean not_registered, not successful empty data', () => {
  const body = 'const dbMenus = []; const dbFacilitiesList = [{"id":1},{"id":2},{"id":3},{"id":4}];';
  assert.deepEqual(parse(body, now), {ok: false, state: 'not_registered'});
});

test('old source data is not publishable', () => {
  assert.equal(parse(fixture, new Date('2026-09-15T01:00:00Z')).state, 'stale_source');
});

test('public status exposes no menu content or private fields', () => {
  const status = publicStatus({state: 'source_error', last_success_at: now.toISOString(), last_good: {menus: [{target_date:'2026-09-14'}]}, private_key: 'DO NOT EXPOSE'});
  assert.equal(status.ok, false);
  assert.equal(status.last_success_at, now.toISOString());
  assert.equal(status.menu_date, '2026-09-14');
  assert.equal('private_key' in status, false);
});

test('KST date boundary', () => {
  assert.equal(kstDay(new Date('2026-09-13T14:59:59Z')), '2026-09-13');
  assert.equal(kstDay(new Date('2026-09-13T15:00:00Z')), '2026-09-14');
});

test('persistent state keeps exact last good content and time on failure', () => {
  const previous = mergeResult({}, {...parse(fixture, now), checked_at: now.toISOString()});
  for (const state of ['source_error', 'schema_error', 'not_registered', 'stale_source']) {
    const next = mergeResult(previous, {ok: false, state, checked_at: '2026-09-15T01:00:00Z'});
    assert.deepEqual(next.last_good, previous.last_good);
    assert.equal(next.last_success_at, previous.last_success_at);
    assert.equal(publicStatus(next).ok, false);
  }
});

test('missing menu dates are schema failure', () => {
  assert.throws(() => parse(fixture.replaceAll('target_date', 'missing_date'), now), /Missing menu dates/);
});

test('missing facility array does not discard valid cafeteria menus', () => {
  const result = parse(fixture.replace('const dbFacilitiesList', 'const changedFacilities'), now);
  assert.equal(result.ok, true);
  assert.equal(result.data.menus.length, 11);
  assert.deepEqual(result.data.facilities, []);
});

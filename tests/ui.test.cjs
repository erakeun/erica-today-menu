const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../dist/index.html'), 'utf8');
const script = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].at(-1)[1];
const fixed = new Date('2026-09-15T03:00:00Z').getTime();
class Clock extends Date { constructor(...args) { super(...(args.length ? args : [fixed])); } static now() { return fixed; } }
function setup() {
  const updated = {};
  const context = vm.createContext({Date:Clock, Intl, URLSearchParams, AbortSignal,
    location:{search:''}, history:{replaceState(){}},
    document:{querySelectorAll:()=>[],querySelector:()=>updated},
    fetch:()=>new Promise(()=>{})});
  vm.runInContext(script, context);
  return {context,updated};
}
test('previous-day unregistered restaurant is not described as today', () => {
  const {context} = setup();
  const markup = vm.runInContext("state.data={date:'2026-09-14'}; restaurantMarkup({name:'식당',meals:[],status:'not_registered'})", context);
  assert.ok(markup.includes('해당 날짜에 등록된 메뉴'));
  assert.ok(!markup.includes('오늘 메뉴 미등록'));
});
test('previous-day relay unregistered status is not reported as today', async () => {
  const {context,updated} = setup();
  context.fetch = async()=>({ok:true,json:async()=>({state:'not_registered',checked_at:'2026-09-14T03:00:00Z'})});
  await vm.runInContext("showSourceStatus({date:'2026-09-14',generated_at:'2026-09-14T03:00:00Z'})",context);
  assert.ok(updated.textContent.includes('원본 갱신 확인 지연'));
  assert.ok(!updated.textContent.includes('오늘 메뉴 미등록'));
});

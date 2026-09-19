// DOM logic tests only. No browser, layout engine, screenshot or game UI is used.
import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {JSDOM} from 'jsdom';
import {setTimeout as delay} from 'node:timers/promises';
let child,dom,base,originalFetch=globalThis.fetch,networkDown=false;
const media={matches:false,addEventListener(){}};
const $=s=>dom.window.document.querySelector(s);
async function until(fn){for(let i=0;i<100;i++){if(fn())return;await delay(20);}assert.fail('Timed out: '+fn);}
before(async()=>{
  child=spawn(process.env.PYTHON||'python',['tests/serve_fixture.py'],{stdio:['ignore','pipe','ignore'],windowsHide:true});
  const port=await new Promise((resolve,reject)=>{child.stdout.once('data',x=>resolve(Number(x.toString().trim())));child.once('error',reject);child.once('exit',code=>reject(new Error(`Fixture server exited: ${code}`)));});
  base=`http://127.0.0.1:${port}`;
  dom=new JSDOM(await readFile('web/static/index.html','utf8'),{url:base+'/?scenario=ce-05&q=%EC%A1%B0%EC%A1%B0'});
  for(const k of ['window','document','location','history','localStorage','FormData'])Object.defineProperty(globalThis,k,{value:dom.window[k],configurable:true});
  globalThis.matchMedia=q=>q.includes('1100')?media:{matches:false,addEventListener(){}};
  dom.window.scrollTo=()=>{};dom.window.HTMLElement.prototype.scrollIntoView=()=>{};
  dom.window.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
  dom.window.HTMLDialogElement.prototype.show=function(){this.open=true;};
  dom.window.HTMLDialogElement.prototype.close=function(){this.open=false;};
  globalThis.fetch=(path,options)=>networkDown?Promise.reject(new TypeError('Offline test')):originalFetch(new URL(path,base),options);
  await import('../web/static/app.js');
});
after(()=>{child?.kill();dom?.window.close();globalThis.fetch=originalFetch;});
test('shared URL, source personality, tactics and direction groups render as DOM',async()=>{
  assert.equal($('#q').value,'조조');assert.match($('#results').textContent,/조조/);
  $('[data-officer="521"]').click();await until(()=>$('#detail-content h2')?.textContent==='조조');
  assert.match($('#personality').textContent,/의리2 \/ 5/);assert.match($('#battle').textContent,/위무지강/);
  assert.match($('#relations').textContent,/내가 친애/);assert.match($('#relations').textContent,/나를 친애/);
  $('[data-close-detail]').click();await until(()=>!$('#detail').open);
});
test('favorite, recent removal, and named search persist without changing source data',async()=>{
  $('[data-favorite="521"]').click();assert.deepEqual(JSON.parse(localStorage.getItem('sam14-ce:v1:favorites')),[521]);
  $('#save-search').click();$('#search-name').value='조조 검색';$('#save-search-form').dispatchEvent(new dom.window.Event('submit',{bubbles:true,cancelable:true}));
  assert.equal(JSON.parse(localStorage.getItem('sam14-ce:v1:searches'))[0].name,'조조 검색');$('#searches-dialog').close();
  $('[data-tab="stash"]').click();await until(()=>$('#results [data-officer="521"]'));
  $('[data-stash="recent"]').click();await until(()=>$('#results [data-remove-recent="521"]'));
  $('[data-remove-recent="521"]').click();await until(()=>JSON.parse(localStorage.getItem('sam14-ce:v1:recent')).length===0);
});
test('comparison, multi-trait serialization and desktop panel logic',async()=>{
  history.replaceState({},'',base+'/?scenario=ce-05&q=%EC%A1%B0%EC%A1%B0&compare=147,521');window.dispatchEvent(new dom.window.PopStateEvent('popstate'));
  await until(()=>!$('#compare-open').disabled);$('#compare-open').click();await until(()=>$('#comparison-content table'));
  assert.match($('#comparison-content').textContent,/관우/);assert.match($('#comparison-content').textContent,/조조/);$('#comparison').close();
  $('#filter-open').click();await until(()=>$('#filters').open);
  for(const o of $('#trait').options)o.selected=['14','196'].includes(o.value);
  $('#filter-form').dispatchEvent(new dom.window.Event('submit',{bubbles:true,cancelable:true}));assert.equal(new URLSearchParams(location.search).get('trait'),'14,196');
  media.matches=true;history.replaceState({},'',base+'/?scenario=ce-05&q=%EC%A1%B0%EC%A1%B0&officer=521');window.dispatchEvent(new dom.window.PopStateEvent('popstate'));
  await until(()=>$('#detail-content h2')?.textContent==='조조');assert.equal($('#detail').dataset.mode,'panel');
  history.replaceState({},'',base+'/?scenario=ce-05');window.dispatchEvent(new dom.window.PopStateEvent('popstate'));await until(()=>$('#results table')&&$('#count').textContent===(process.env.CE_TEST_DATABASE?'1,000명':'3명'));
});
test('QR stays local and stale responses are visibly identified',async()=>{
  $('#share-page').click();$('#share-origin').value='https://example.com';$('#make-qr').click();
  assert.ok($('#qr-output svg'));assert.match($('#share-url').textContent,/https:\/\/example.com/);$('#share-dialog').close();
  // Expire cache by moving the application's clock, then simulate network loss.
  const realNow=Date.now;Date.now=()=>realNow()+120000;networkDown=true;
  history.replaceState({},'',base+'/?scenario=ce-05&q=%EC%A1%B0%EC%A1%B0');window.dispatchEvent(new dom.window.PopStateEvent('popstate'));
  await until(()=>!$('#cache-status').hidden);assert.match($('#cache-status').textContent,/저장한 결과/);
  networkDown=false;Date.now=realNow;
});
test('DLC selection and new codices remain usable without officer filter buttons',async()=>{
  history.replaceState({},'',base+'/?scenario=ce-32');window.dispatchEvent(new dom.window.PopStateEvent('popstate'));
  await until(()=>$('#scenario').value==='ce-32'&&$('#results [data-officer]'));
  $('[data-tab="codex"]').click();await until(()=>!$('#codex-controls').hidden);
  for(const kind of ['scenic','strategy','literature','merit']){
    $(`[data-codex="${kind}"]`).click();
    await until(()=>$('#results .codex-card')&&!$('#results [data-codex-filter]'));
    assert.ok($('#results .codex-card h3').textContent);
  }
  $('[data-codex="policy"]').click();await until(()=>$('#results .level-effects'));
  assert.match($('#results .level-effects').textContent,/개인 정책 레벨/);
  assert.match($('#results .level-effects').textContent,/단위/);
});

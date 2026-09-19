import test from 'node:test';
import assert from 'node:assert/strict';
import {QueryCache,cleanIds,selectedIds,searchContext} from '../web/static/state.mjs';
import qrcode from '../web/static/vendor/qrcode.mjs';
test('cache expires, bounds memory, isolates release and scenario',()=>{
  let now=0;const cache=new QueryCache(2,100,()=>now);cache.selectRelease('r1');
  cache.put('officers?scenario=a',{name:'a'});cache.put('officers?scenario=b',{name:'b'});
  assert.equal(cache.get('officers?scenario=a').value.name,'a');cache.put('c',{});assert.equal(cache.get('officers?scenario=b'),null);
  now=101;assert.equal(cache.get('officers?scenario=a'),null);assert.equal(cache.get('officers?scenario=a',{stale:true}).stale,true);
  cache.selectRelease('r2');assert.equal(cache.get('officers?scenario=a',{stale:true}),null);
});
test('stored IDs reject bad input and saved searches omit detail state',()=>{
  assert.deepEqual(cleanIds([1,1,-1,0,'2',2,NaN]),[1,2]);assert.deepEqual(selectedIds('147,521,147,bad,0,952,656'),[147,521,952]);
  assert.equal(searchContext('scenario=ce-05&trait=1%2C2&officer=521&tab=stash&compare=147%2C521&page=9'),'scenario=ce-05&trait=1%2C2');
});
test('QR encodes a complete URL locally with sufficient quiet zone',()=>{
  const url=new URL('https://example.com/?q=조조&scenario=ce-05&officer=521');
  assert.equal([...url.href].every(x=>x.charCodeAt(0)<128),true);
  const qr=qrcode(0,'M');qr.addData(url.href);qr.make();const svg=qr.createSvgTag({cellSize:4,margin:16,scalable:true});
  assert.ok(qr.getModuleCount()>21);assert.match(svg,/<svg/);assert.match(svg,/viewBox=/);assert.doesNotMatch(svg,/<script|href=|src=/);
});

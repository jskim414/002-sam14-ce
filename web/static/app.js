import {cleanIds,selectedIds,searchContext,QueryCache} from './state.mjs';
import qrcode from './vendor/qrcode.mjs';
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const statKeys = ['leadership','strength','intelligence','politics','charisma'];
const statLabels = ['통솔','무력','지력','정치','매력'];
const filterKeys = ['state','force','doctrine','policy','level_min','trait','trait_mode','formation','tactic','kind'];
const storageKey = 'sam14-ce:v1:';
function read(key, fallback) { try { return JSON.parse(localStorage.getItem(storageKey + key)) ?? fallback; } catch { return fallback; } }
function save(key, value) { try { localStorage.setItem(storageKey + key, JSON.stringify(value)); } catch { /* In-memory use remains available. */ } }
let favorites = read('favorites', []), recent = read('recent', []);
if (!Array.isArray(favorites)) favorites = [];
if (!Array.isArray(recent)) recent = [];
favorites = cleanIds(favorites,100); recent = cleanIds(recent,20);
let meta, scenarios, coverage, listController, detailController, listVersion = 0, detailVersion = 0;
let total = 0, stashMode = 'favorites', codexKind = 'trait', composing = false, timer, activeDetail;
let detailOrigin, lastListKey, suggestionController, suggestionVersion=0, comparisonController;
let savedSearches=read('searches',[]);
if(!Array.isArray(savedSearches))savedSearches=[];
savedSearches=savedSearches.filter(x=>x&&typeof x.name==='string'&&typeof x.query==='string').slice(0,20);
const cache=new QueryCache();
const wide=matchMedia('(min-width:1100px)');
const params = () => new URLSearchParams(location.search);
const scenarioId = () => params().get('scenario') || meta?.default_scenario || 'ce-05';
const tab = () => params().get('tab') || 'officers';
const dictionary = k => meta[k === 'policy' ? 'policies' : k + 's'] || [];

async function api(path, signal) {
  const cacheable=!['meta','health','coverage','scenarios'].includes(path);
  const hit=cacheable&&cache.get(path);
  if(hit)return hit.value;
  let response;
  try{response=await fetch('/api/v1/' + path, {signal});}
  catch(error){
    if(error.name==='AbortError')throw error;
    const previous=cacheable&&cache.get(path,{stale:true});
    if(previous){$('#cache-status').hidden=false;$('#cache-status').textContent=`연결 오류로 ${new Date(previous.time).toLocaleTimeString()}에 저장한 결과를 표시합니다. 다시 시도로 최신 데이터를 확인하세요.`;$('#retry').hidden=false;return previous.value;}
    throw error;
  }
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || '데이터를 불러오지 못했습니다.');
  if(cacheable){if(body.release_id&&body.release_id!==meta?.release_id)throw new Error('데이터 버전이 변경되었습니다. 페이지를 새로 열어주세요.');cache.put(path,body);}
  return body;
}
function showError(error) { $('#error').textContent = error.message; $('#error').hidden = false; $('#retry').hidden = false; }
function clearError() { $('#error').hidden = true; $('#retry').hidden = true;$('#cache-status').hidden=true; }
function remember() {save('context',searchContext(params()));}
function navigate(changes, {replace=false}={}) {
  const p = params();
  for (const [k,v] of Object.entries(changes)) v === null || v === '' ? p.delete(k) : p.set(k,String(v));
  if (!replace) history.replaceState({...history.state,scroll:window.scrollY},'',location.href);
  const state={scroll:0,openedByApp:!!changes.officer};
  history[replace?'replaceState':'pushState'](state,'','/?'+p.toString());
  remember(); render();
}
function stats(row) { return `<div class="stats">${statKeys.map((k,i)=>`<div><span class="stat-label">${statLabels[i]}</span><strong class="stat-value">${esc(row[k])}</strong></div>`).join('')}</div>`; }
function policy(row) { return `${esc(row.doctrine || '주의 미확인')} · <b>${esc(row.policy || '정책 미확인')}</b> · ${row.policy_level == null ? '레벨 미확인' : 'Lv.'+esc(row.policy_level)}`; }
function favoriteButton(id) { return `<button class="favorite" data-favorite="${id}" aria-pressed="${favorites.includes(id)}" aria-label="즐겨찾기 ${favorites.includes(id)?'해제':'추가'}">${favorites.includes(id)?'★':'☆'}</button>`; }
function compareButton(id){return `<button data-compare="${id}" aria-pressed="${selectedIds(params().get('compare')).includes(id)}">비교</button>`;}
function itemActions(id){return `<div class="item-actions">${compareButton(id)}${tab()==='stash'&&stashMode==='recent'?`<button data-remove-recent="${id}">최근 조회에서 삭제</button>`:''}</div>`;}
function card(row) {
  return `<article class="card"><div class="card-title"><button class="name-button" data-officer="${row.officer_id}">${esc(row.name)}</button>${favoriteButton(row.officer_id)}</div><p class="subtitle">${esc(row.courtesy_name)} · ${esc(row.state_label)} · ${esc(row.force_name ? row.force_name+' 세력' : row.settlement_name || '위치 미확인')}${row.state==='UNAPPEARED'&&row.appearance_year?' · '+esc(row.appearance_year)+'년 등장':''}</p>${stats(row)}<p class="policy-line">${policy(row)}</p><div class="tags">${row.traits.slice(0,5).map(t=>`<button class="tag" data-filter-trait="${t.id}">${esc(t.name)}</button>`).join('')}</div>${itemActions(row.officer_id)}</article>`;
}
function table(rows){return `<div class="table-wrap"><table class="officer-table"><thead><tr><th>무장 · 소속</th>${statLabels.map(x=>`<th>${x}</th>`).join('')}<th>주의 · 정책 · 레벨</th><th>보관·비교</th></tr></thead><tbody>${rows.map(r=>`<tr><td><button class="name-button" data-officer="${r.officer_id}">${esc(r.name)}</button><div class="subtitle">${esc(r.courtesy_name)} · ${esc(r.state_label)}<br>${esc(r.force_name||r.settlement_name||'위치 미확인')}</div></td>${statKeys.map(k=>`<td>${esc(r[k])}</td>`).join('')}<td>${policy(r)}</td><td>${favoriteButton(r.officer_id)}${itemActions(r.officer_id)}</td></tr>`).join('')}</tbody></table></div>`;}
function setOptions(element,rows,placeholder,value) { element.innerHTML = `<option value="">${placeholder}</option>`+rows.map(r=>`<option value="${esc(r.id)}">${esc(r.name)}</option>`).join('');element.value=value || ''; }
function syncControls() {
  const p=params();$('#q').value=p.get('q')||'';$('#scenario').value=scenarioId();$('#sort').value=p.get('sort')||'name';
  $('#page-title').textContent={officers:'필요한 무장을, 바로.',codex:'특징에서 무장으로.',stash:'다시 찾는 무장들.'}[tab()] || '무장 참조';
  $('#page-description').textContent={officers:'능력부터 정책과 인간관계까지 살펴보세요.',codex:'개성·정책·진형을 골라 보유 무장을 찾으세요.',stash:'이 기기에서 저장하거나 최근 살펴본 무장입니다.'}[tab()] || '';
  $('#q').placeholder=tab()==='codex'?'도감 이름을 입력하세요':'무장 이름 또는 자를 입력하세요';
  $('#quick').hidden=tab()!=='officers';$('#stash-controls').hidden=tab()!=='stash';$('#codex-controls').hidden=tab()!=='codex';
  $('#filter-open').hidden=tab()==='codex';$('#sort-label').hidden=tab()==='codex';
  const comparison=selectedIds(p.get('compare'));$('#compare-bar').hidden=!comparison.length;$('#compare-count').textContent=`${comparison.length} / 3명 선택`;$('#compare-open').disabled=comparison.length<2;
  $('#filter-count').textContent=filterKeys.filter(k=>p.has(k)&&!(k==='kind'&&p.get(k)==='HISTORICAL')).length || '';
  document.querySelectorAll('[data-state]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.state===(p.get('state')||''))));
  document.querySelectorAll('[data-tab]').forEach(b=>{if(b.dataset.tab===tab())b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
  document.querySelectorAll('[data-stash]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.stash===stashMode)));
  document.querySelectorAll('[data-codex]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.codex===codexKind)));
}
async function render() {
  if(!meta)return;
  syncControls();clearError();listController?.abort();listController=new AbortController();const version=++listVersion;
  const p=params();const selected=p.get('officer');
  if(selected) openDetail(Number(selected));else{detailController?.abort();detailVersion++;activeDetail=null;if($('#detail').open)$('#detail').close();document.body.classList.remove('has-detail');}
  const listParams=new URLSearchParams(p);listParams.delete('officer');
  const listKey=JSON.stringify([listParams.toString(),stashMode,codexKind,tab()==='stash'?[favorites,recent]:[]]);
  if(tab()==='officers'&&lastListKey===listKey){$('#results').classList.remove('loading');if(!selected){window.scrollTo(0,history.state?.scroll||0);detailOrigin?.focus?.({preventScroll:true});}return;}
  if(tab()==='codex') {
    let full;try{full=await api((codexKind==='policy'?'policies':codexKind+'s'),listController.signal);}catch(error){if(error.name!=='AbortError')showError(error);return;}if(version!==listVersion)return;
    const rows=full.items.filter(x=>x.name.includes(p.get('q')||''));
    $('#count').textContent=`${rows.length}개 항목`;$('#pagination').hidden=true;
    $('#results').innerHTML=rows.map(r=>`<article class="card codex-card"><h3>${esc(r.name)}</h3><p class="muted">${esc(r.description||'원천 효과 설명 미수록')}</p>${r.components?.length?`<details><summary>포함 효과</summary>${r.components.map(x=>`<p class="muted"><b>${esc(x.name)}</b> · ${esc(x.description||'')}</p>`).join('')}</details>`:''}<button data-codex-filter="${codexKind}:${r.id}">보유 무장 보기 →</button></article>`).join('') || '<p class="empty">일치하는 항목이 없습니다.</p>';
    $('#results').classList.remove('loading');return;
  }
  $('#results').classList.add('loading');$('#count').textContent='검색 중…';
  const query=new URLSearchParams({scenario:scenarioId(),page_size:'30'});
  for(const key of ['q','sort','page',...filterKeys])if(p.has(key))query.set(key,p.get(key));
  if(query.get('sort')&&!['name','appearance_year'].includes(query.get('sort')))query.set('order','desc');
  if(tab()==='stash'){const ids=stashMode==='recent'?recent:favorites;query.set('ids',ids.join(','));query.set('kind','ALL');if(stashMode==='recent'&&ids.length)query.set('sort','input');}
  try {
    const data=await api('officers?'+query,listController.signal);if(version!==listVersion)return;
    lastListKey=listKey;total=data.total;$('#count').textContent=`${total.toLocaleString()}명${tab()==='stash'?' · 현재 검색 조건 기준':''}`;
    $('#results').innerHTML=(data.items.length?(wide.matches?table(data.items):data.items.map(card).join('')):'') || `<p class="empty">${tab()==='stash'?'보관함에 무장을 추가해 보세요.<br>이미 저장한 무장이 없다면 검색 조건을 확인해주세요.':'조건에 맞는 무장이 없습니다.<br>검색어나 필터를 바꿔보세요.'}</p>`;
    $('#pagination').hidden=total<=30;$('#page').textContent=`${data.page} / ${Math.max(1,Math.ceil(total/30))}`;
    $('#previous').disabled=data.page<=1;$('#next').disabled=data.page*30>=total;
    if(!selected&&history.state?.scroll)window.scrollTo(0,history.state.scroll);
  } catch(error) {if(error.name!=='AbortError'&&version===listVersion){showError(error);$('#count').textContent='검색을 완료하지 못했습니다.';}}
  finally{if(version===listVersion)$('#results').classList.remove('loading');}
}
function closeDetail() {
  if(history.state?.openedByApp) history.back();else navigate({officer:null},{replace:true});
  detailOrigin?.focus?.();
}
async function openDetail(id) {
  if(!Number.isSafeInteger(id)||id<=0){showError(new Error('무장 주소가 올바르지 않습니다.'));return;}
  detailController?.abort();detailController=new AbortController();const version=++detailVersion;
  const dialog=$('#detail');const mode=wide.matches?'panel':'modal';
  if(dialog.open&&dialog.dataset.mode!==mode)dialog.close();
  if(!dialog.open){detailOrigin=document.activeElement;dialog.dataset.mode=mode;if(wide.matches)dialog.show();else dialog.showModal();}
  document.body.classList.add('has-detail');
  $('#detail-content').innerHTML='<div class="dialog-head"><h2>무장 정보</h2><button class="icon" data-close-detail aria-label="상세 닫기">×</button></div><p class="muted">불러오는 중…</p>';
  try {
    const row=await api(`officers/${id}?scenario=${encodeURIComponent(scenarioId())}`,detailController.signal);
    if(version!==detailVersion)return;activeDetail=row;recent=[id,...recent.filter(x=>x!==id)].slice(0,20);save('recent',recent);
    const groups=[['outgoing','AFFINITY','내가 친애하는 무장'],['incoming','AFFINITY','나를 친애하는 무장'],['outgoing','DISLIKE','내가 혐오하는 무장'],['incoming','DISLIKE','나를 혐오하는 무장'],['outgoing','MARRIAGE','배우자'],['outgoing','SWORN_SIBLING','의형제']];
    $('#detail-content').innerHTML=`<div class="detail-hero"><div><p class="eyebrow">CE · 시나리오 시작 데이터</p><h2>${esc(row.name)}</h2><p class="subtitle">${esc(row.courtesy_name)} · ${esc(row.state_label)}<br>${esc(row.force_name?row.force_name+' 세력':'소속 세력 없음')} · ${esc(row.settlement_name||'위치 미확인')}</p></div><div>${favoriteButton(id)}<button class="icon" data-close-detail aria-label="이전 화면">×</button></div></div>
    <nav class="detail-nav" aria-label="상세 섹션"><button data-section="summary">요약</button><button data-section="personality">내면</button><button data-section="relations">관계</button><button data-section="battle">전투</button></nav>
    <section id="summary" class="detail-section">${stats(row)}<p class="policy-line">${policy(row)}</p><p class="muted">${esc(row.policy_detail?.description||'')}</p>${row.policy_detail?.components?.length?`<details><summary>정책에 포함된 효과</summary>${row.policy_detail.components.map(x=>`<p class="muted"><b>${esc(x.name)}</b> · ${esc(x.description||'')}</p>`).join('')}</details>`:''}<div class="fact-grid"><p><span>등장</span><strong>${esc(row.appearance_year??'미확인')}${row.appearance_year?'년':''}</strong></p><p><span>생몰년</span><strong>${esc(row.birth_year??'?')}–${esc(row.death_year??'?')}</strong></p><p><span>상성</span><strong>${esc(row.affinity??'미확인')}</strong></p></div></section>
    <section id="personality" class="detail-section"><h3>내면</h3><div class="personality-grid">${row.personality.map(x=>`<div><span>${esc(x.label)}</span><b>${x.value==null?'확인 중':esc(x.value)+' / 5'}</b></div>`).join('')}</div><p class="muted">내면은 원천 수치와 형식 연구를 교차 검증한 값입니다. 게임 화면 대조는 제외되어 있습니다. 미확인은 숫자로 바꾸지 않습니다.</p></section>
    <section id="relations" class="detail-section"><h3>인간관계</h3><p class="muted">선택한 시나리오의 방향별 관계입니다. 게임 화면 대조는 아직 완료되지 않았습니다.</p>${groups.map(([direction,type,title])=>{const items=row.relationships[direction].filter(x=>x.type===type);return `<div class="relationship-group"><h4>${title}</h4><div class="tags">${items.length?items.map(x=>`<button class="tag" data-officer="${x.target_id}">${esc(x.target_name)}${x.courtesy_name?' · '+esc(x.courtesy_name):''}</button>`).join(''):'<span class="muted">원천 슬롯에 대상 없음 · 검증 대기</span>'}</div></div>`;}).join('')}<p class="muted">배우자는 원천의 직접 참조, 의형제는 같은 장형 ID를 가진 그룹입니다.</p></section>
    <section id="battle" class="detail-section"><h3>개성</h3><div class="tags">${row.traits.map(t=>`<button class="tag" data-detail-filter="trait:${t.id}">${esc(t.name)}</button>`).join('')||'<span class="muted">원천 슬롯에 없음</span>'}</div><h3 class="detail-section">진형</h3><div class="tags">${row.formations.map(t=>`<button class="tag" data-detail-filter="formation:${t.id}">${esc(t.name)}</button>`).join('')||'<span class="muted">원천 슬롯에 없음</span>'}</div><h3 class="detail-section">전법</h3><div class="tags">${row.tactics.map(t=>`<button class="tag" data-detail-filter="tactic:${t.id}">${esc(t.name)}</button>`).join('')||'<span class="muted">원천 슬롯에 없음</span>'}</div><details><summary>개성·진형 설명</summary>${[...row.traits,...row.formations].filter(x=>x.description).map(x=>`<p class="muted"><b>${esc(x.name)}</b> · ${esc(x.description)}</p>`).join('')}</details></section>
    <section class="detail-section"><h3>데이터 정보</h3><p class="evidence">${esc(meta.release_id)}<br>${esc(row.evidence.relative_path)}<br>원천 ID ${row.officer_id} · 해제 데이터 위치 ${row.record_offset}<br>검증 상태: 원천 레코드 추출, 게임 화면 대조 대기</p><button id="copy-link">현재 무장 링크 복사</button><button data-share-detail>QR로 이어보기</button><p id="copy-status" class="muted" role="status"></p></section>`;
    dialog.scrollTop=0;dialog.querySelector('[data-close-detail]').focus();
  }catch(error){if(error.name!=='AbortError'&&version===detailVersion)$('#detail-content').innerHTML=`<div class="dialog-head"><h2>정보를 열 수 없습니다</h2><button class="icon" data-close-detail aria-label="닫기">×</button></div><p class="error">${esc(error.message)}</p>`;}
}
async function openFilters() {
  const p=params();$('#filters').showModal();
  for(const key of filterKeys){const control=$(`#filter-form [name="${key}"]`);if(control?.multiple){const values=(p.get(key)||'').split(',');[...control.options].forEach(o=>o.selected=values.includes(o.value));}else if(control)control.value=p.get(key)||(key==='kind'?'HISTORICAL':key==='trait_mode'?'all':'');}
  const sid=scenarioId();
  try {const result=await api('forces?scenario='+encodeURIComponent(sid));if(sid===scenarioId())setOptions($('#force'),result.items,'전체 세력',p.get('force'));}catch(error){showError(error);}
}
function hideSuggestions(){suggestionController?.abort();suggestionVersion++;$('#suggestions').hidden=true;$('#q').setAttribute('aria-expanded','false');$('#q').removeAttribute('aria-activedescendant');}
async function suggest(){
  suggestionController?.abort();const version=++suggestionVersion;const q=$('#q').value.trim();
  if(!q||composing||tab()==='codex'){hideSuggestions();return;}
  suggestionController=new AbortController();
  try{
    const result=await api('officers?'+new URLSearchParams({scenario:scenarioId(),q,page_size:'8',kind:params().get('kind')||'HISTORICAL'}),suggestionController.signal);
    if(version!==suggestionVersion)return;
    $('#suggestions').innerHTML=result.items.map((r,i)=>`<button role="option" aria-selected="false" id="suggestion-${i}" data-officer="${r.officer_id}"><b>${esc(r.name)}</b><span>${esc(r.courtesy_name||'자 미수록')} · ${esc(r.force_name||r.settlement_name||r.state_label)} · ID ${r.officer_id}</span></button>`).join('');
    $('#suggestions').hidden=!result.items.length;$('#q').setAttribute('aria-expanded',String(!!result.items.length));
  }catch(error){if(error.name!=='AbortError')hideSuggestions();}
}
function savedSearchList(){
  $('#searches-list').innerHTML=savedSearches.map((x,i)=>`<div class="saved-row"><button data-load-search="${i}">${esc(x.name)}</button><button data-delete-search="${i}" aria-label="${esc(x.name)} 삭제">삭제</button></div>`).join('')||'<p class="muted">저장한 검색이 없습니다.</p>';
}
async function showComparison(){
  comparisonController?.abort();comparisonController=new AbortController();
  const ids=selectedIds(params().get('compare'));if(ids.length<2)return;
  $('#comparison').showModal();$('#comparison-content').textContent='비교 정보를 불러오는 중…';
  try{
    const result=await api('compare?'+new URLSearchParams({scenario:scenarioId(),ids:ids.join(',')}),comparisonController.signal);
    const rows=result.items;const fields=[...statKeys.map((k,i)=>[statLabels[i],r=>r[k]]),['주의',r=>r.doctrine],['정책',r=>r.policy],['정책 레벨',r=>r.policy_level],...['integrity','diplomacy','han_attitude','ambition','aggression'].map(k=>[rows[0].personality.find(x=>x.key===k).label,r=>r.personality.find(x=>x.key===k).value]),['개성',r=>r.traits.map(x=>x.name).join(' · ')],['진형',r=>r.formations.map(x=>x.name).join(' · ')],['전법',r=>r.tactics.map(x=>x.name).join(' · ')]];
    $('#comparison-content').innerHTML=`<p class="muted">${esc(scenarios.items.find(x=>x.id===scenarioId())?.name)} 시작 기준 · 색 표시: 값이 다른 항목</p><div class="table-wrap"><table class="compare-table"><thead><tr><th>항목</th>${rows.map(r=>`<th>${esc(r.name)}<br><small>${esc(r.courtesy_name)}</small></th>`).join('')}</tr></thead><tbody>${fields.map(([label,get])=>{const values=rows.map(get),different=new Set(values).size>1;return `<tr class="${different?'different':''}"><th>${label}${different?'<span class="sr-only"> · 차이 있음</span>':''}</th>${values.map(x=>`<td>${esc(x??'미확인')}</td>`).join('')}</tr>`;}).join('')}</tbody></table></div>`;
  }catch(error){if(error.name!=='AbortError')$('#comparison-content').textContent=error.message;}
}
function showShare(){
  $('#share-origin').value=read('share-origin',location.origin);$('#share-dialog').showModal();makeQr();
}
function makeQr(){
  try{
    const origin=new URL($('#share-origin').value);if(!['http:','https:'].includes(origin.protocol)||origin.username||origin.password)throw new Error('http 또는 https 서비스 주소를 입력해주세요.');
    const url=new URL(location.pathname+location.search,origin.origin);if(url.href.length>1800)throw new Error('조건이 너무 길어 QR을 만들 수 없습니다. 필터를 줄여주세요.');
    const qr=qrcode(0,'M');qr.addData(url.href);qr.make();
    $('#qr-output').innerHTML=qr.createSvgTag({cellSize:4,margin:16,scalable:true});$('#qr-output').querySelector('svg').setAttribute('aria-label','현재 조건을 여는 QR 코드');
    $('#share-url').textContent=url.href;$('#share-status').textContent='QR은 이 기기에서 생성하며 외부로 전송하지 않습니다.';save('share-origin',origin.origin);
  }catch(error){$('#qr-output').replaceChildren();$('#share-url').textContent='';$('#share-status').textContent=error.message;}
}
$('#save-search-form').addEventListener('submit',event=>{
  event.preventDefault();const name=$('#search-name').value.trim();if(!name)return;
  savedSearches=[{name,query:searchContext(params())},...savedSearches.filter(x=>x.name!==name)].slice(0,20);save('searches',savedSearches);savedSearchList();$('#search-name').value='';
});
$('#q').addEventListener('keydown',event=>{
  const options=[...$('#suggestions').querySelectorAll('[role=option]')];if($('#suggestions').hidden)return;
  if(event.key==='Escape'){hideSuggestions();return;}
  let index=options.findIndex(x=>x.id===$('#q').getAttribute('aria-activedescendant'));
  if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();index=(index+(event.key==='ArrowDown'?1:-1)+options.length)%options.length;options.forEach((x,i)=>x.setAttribute('aria-selected',String(i===index)));$('#q').setAttribute('aria-activedescendant',options[index].id);}
  if(event.key==='Enter'&&index>=0){event.preventDefault();options[index].click();}
});
wide.addEventListener('change',()=>{lastListKey=null;render();});
document.addEventListener('click',async event=>{
  const b=event.target.closest('button');if(!b)return;
  if(b.dataset.officer){hideSuggestions();navigate({officer:b.dataset.officer});return;}
  if(b.dataset.compare){const id=Number(b.dataset.compare),ids=selectedIds(params().get('compare'));if(ids.includes(id))ids.splice(ids.indexOf(id),1);else if(ids.length<3)ids.push(id);else{showError(new Error('비교는 최대 3명까지 가능합니다.'));return;}navigate({compare:ids.join(',')},{replace:true});return;}
  if(b.dataset.removeRecent){recent=recent.filter(x=>x!==Number(b.dataset.removeRecent));save('recent',recent);render();return;}
  if(b.hasAttribute('data-load-search')){const entry=savedSearches[Number(b.dataset.loadSearch)];if(entry){$('#searches-dialog').close();history.pushState({scroll:0},'','/?'+searchContext(entry.query));remember();render();}return;}
  if(b.hasAttribute('data-delete-search')){savedSearches.splice(Number(b.dataset.deleteSearch),1);save('searches',savedSearches);savedSearchList();return;}
  if(b.id==='save-search'||b.id==='saved-searches'){savedSearchList();$('#searches-dialog').showModal();if(b.id==='save-search')$('#search-name').focus();return;}
  if(b.id==='compare-open'){showComparison();return;}
  if(b.id==='compare-clear'){navigate({compare:null},{replace:true});return;}
  if(b.id==='share-page'||b.hasAttribute('data-share-detail')){showShare();return;}
  if(b.id==='make-qr'){makeQr();return;}
  if(b.id==='copy-share'){try{if(!$('#share-url').textContent)return;await navigator.clipboard.writeText($('#share-url').textContent);$('#share-status').textContent='링크를 복사했습니다.';}catch{$('#share-status').textContent='위 링크를 직접 복사해주세요.';}return;}
  if(b.dataset.favorite){const id=Number(b.dataset.favorite);favorites=favorites.includes(id)?favorites.filter(x=>x!==id):[id,...favorites].slice(0,100);save('favorites',favorites);document.querySelectorAll(`[data-favorite="${id}"]`).forEach(x=>{x.textContent=favorites.includes(id)?'★':'☆';x.setAttribute('aria-pressed',String(favorites.includes(id)));x.setAttribute('aria-label',favorites.includes(id)?'즐겨찾기 해제':'즐겨찾기 추가');});if(tab()==='stash'&&!$('#detail').open)render();return;}
  if(b.hasAttribute('data-close-detail')){closeDetail();return;}
  if(b.dataset.close){$('#'+b.dataset.close).close();return;}
  if(b.dataset.section){$('#'+b.dataset.section).scrollIntoView({behavior:'auto',block:'start'});return;}
  if(b.dataset.tab){navigate({tab:b.dataset.tab,q:null,page:null,officer:null});return;}
  if(b.id==='upcoming'){navigate({tab:'officers',state:'UNAPPEARED',sort:'appearance_year',q:null,page:null,officer:null});return;}
  if(b.hasAttribute('data-state')){navigate({state:b.dataset.state,page:null});return;}
  if(b.dataset.stash){stashMode=b.dataset.stash;navigate({page:null});return;}
  if(b.dataset.codex){codexKind=b.dataset.codex;render();return;}
  const filter=b.dataset.codexFilter || b.dataset.detailFilter;
  if(filter){const [kind,id]=filter.split(':');navigate({tab:'officers',[kind]:id,q:null,page:null,officer:null});return;}
  if(b.dataset.filterTrait){navigate({trait:b.dataset.filterTrait,page:null});return;}
  if(b.id==='filter-open')await openFilters();
  if(b.id==='reset-filters'){for(const key of filterKeys){const c=$(`#filter-form [name="${key}"]`);if(c?.multiple)[...c.options].forEach(o=>o.selected=false);else if(c)c.value=key==='kind'?'HISTORICAL':key==='trait_mode'?'all':'';}}
  if(b.id==='previous')navigate({page:Math.max(1,Number(params().get('page')||1)-1)});
  if(b.id==='next')navigate({page:Number(params().get('page')||1)+1});
  if(b.id==='retry'){cache.clear();lastListKey=null;if(meta)render();else initialize();}
  if(b.id==='coverage')$('#data-info').showModal();
  if(b.id==='clear-favorites'){favorites=[];save('favorites',favorites);lastListKey=null;render();}
  if(b.id==='clear-recent'){recent=[];save('recent',recent);render();}
  if(b.id==='theme'){const dark=document.documentElement.dataset.theme!=='dark';document.documentElement.dataset.theme=dark?'dark':'light';save('theme',dark?'dark':'light');}
  if(b.id==='copy-link'){try{await navigator.clipboard.writeText(location.href);$('#copy-status').textContent='링크를 복사했습니다.';}catch{$('#copy-status').textContent='주소창의 링크를 복사해주세요.';}}
});
$('#detail').addEventListener('cancel',e=>{e.preventDefault();closeDetail();});
$('#filter-form').addEventListener('submit',e=>{e.preventDefault();const changes=Object.fromEntries(new FormData(e.target));changes.trait=[...$('#trait').selectedOptions].map(x=>x.value).filter(Boolean).join(',');if(changes.trait_mode==='all')changes.trait_mode='';changes.page=null;$('#filters').close();navigate(changes);});
$('#scenario').addEventListener('change',()=>{hideSuggestions();if(params().has('force'))$('#context-status').textContent='시나리오가 바뀌어 이전 세력 필터를 해제했습니다.';navigate({scenario:$('#scenario').value,force:null,page:null,officer:null});});
$('#sort').addEventListener('change',()=>navigate({sort:$('#sort').value,page:null}));
function search(){clearTimeout(timer);timer=setTimeout(()=>{if(!composing){navigate({q:$('#q').value,page:null},{replace:true});suggest();}},150);}
$('#q').addEventListener('compositionstart',()=>{composing=true;clearTimeout(timer);});
$('#q').addEventListener('compositionend',()=>{composing=false;search();});$('#q').addEventListener('input',()=>{if(!composing)search();});
window.addEventListener('popstate',()=>{hideSuggestions();render();});
window.addEventListener('focus',async()=>{if(!meta)return;try{const health=await api('health');if(health.release_id!==meta.release_id||health.parser_sha256!==meta.parser_sha256){cache.clear();lastListKey=null;await initialize();}}catch{/* A failed refresh does not discard visible results. */}});
const savedTheme=read('theme',null);document.documentElement.dataset.theme=savedTheme|| (matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');
async function initialize(){try{
  [meta,scenarios,coverage]=await Promise.all([api('meta'),api('scenarios'),api('coverage')]);
  if(!location.search){const saved=read('context','');if(typeof saved==='string'&&saved)history.replaceState({},'','/?'+saved);}
  if(!params().has('scenario')){const p=params();p.set('scenario',meta.default_scenario);history.replaceState(history.state,'','/?'+p);}
  $('#scenario').innerHTML=scenarios.items.filter(s=>s.mode==='STANDARD'||s.status==='PENDING').map(s=>`<option value="${esc(s.id)}" ${s.status!=='PARSED_REVIEW'?'disabled':''}>${esc(s.name)}${s.start_year?' · '+s.start_year+'년 '+s.start_month+'월':' · 확인 중'}</option>`).join('');
  cache.selectRelease(meta.release_id+':'+meta.parser_sha256);
  for(const kind of ['doctrine','policy','trait','formation','tactic'])setOptions($('#'+kind),dictionary(kind),'전체',null);
  setOptions($('#state'),Object.entries(meta.states).map(([id,name])=>({id,name})),'전체',null);
  $('#build').textContent=`CE build ${meta.build_id} · 검증 중`;
  $('#coverage-content').innerHTML=`<p class="muted">${esc(coverage.release_id)} · ${esc(coverage.data_as_of.slice(0,10))}<br>정식 공개 전 검증 중인 로컬 제품입니다.</p><ul class="notes-list">${coverage.blockers.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`;
  await render();
}catch(error){meta=null;showError(error);$('#count').textContent='초기 데이터를 불러오지 못했습니다.';}}
await initialize();

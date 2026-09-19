export function cleanIds(value,limit=100){return [...new Set((Array.isArray(value)?value:[]).filter(x=>Number.isSafeInteger(x)&&x>0))].slice(0,limit);}
export function selectedIds(value,limit=3){return cleanIds(String(value||'').split(',').filter(x=>/^\d+$/.test(x)).map(Number),limit);}
export function searchContext(value){const p=new URLSearchParams(value);for(const k of ['officer','tab','compare','page'])p.delete(k);return p.toString();}
export class QueryCache{
  constructor(limit=60,ttl=60000,clock=()=>Date.now()){this.limit=limit;this.ttl=ttl;this.clock=clock;this.release=null;this.rows=new Map();}
  selectRelease(release){if(this.release!==release){this.rows.clear();this.release=release;}}
  put(key,value){if(!this.release)return;this.rows.delete(key);this.rows.set(key,{value,time:this.clock()});while(this.rows.size>this.limit)this.rows.delete(this.rows.keys().next().value);}
  get(key,{stale=false}={}){const row=this.rows.get(key);if(!row||(!stale&&this.clock()-row.time>this.ttl))return null;this.rows.delete(key);this.rows.set(key,row);return {...row,stale:this.clock()-row.time>this.ttl};}
  clear(){this.rows.clear();}
}

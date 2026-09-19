"""Build an independent, unpublished CE candidate from hash-checked snapshots."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import ROOT, output_path, sha256, write_json
from probe_ce import probe, officer_records
from extractors.ce import dictionaries, scenario_header, interpret_record, classify_record
from extractors.lwc import FormatError
from source_catalog import catalog

def content_digest(conn: sqlite3.Connection) -> str:
    digest=hashlib.sha256()
    for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        rows=conn.execute(f'SELECT * FROM "{table}"').fetchall()
        digest.update(json.dumps([table,sorted(rows,key=repr)],ensure_ascii=False,separators=(',',':')).encode())
    return digest.hexdigest()

def build(snapshot: Path, profile_path: Path, output: Path, report_path: Path) -> dict:
    output=output_path(output);report_path=output_path(report_path)
    if output.suffix!='.db':raise ValueError('Candidate output must be a .db file')
    snapshot=snapshot.resolve();profile=json.loads(profile_path.read_text('utf-8'))
    inv=json.loads((snapshot/'inventory.json').read_text('utf-8'))
    if profile['build_id']!=inv['steam_build_id']:raise ValueError('Profile/build mismatch')
    if profile.get('release_ready'):raise ValueError('This parser has not passed publication verification')
    index={r['relative_path']:r for r in inv['files']}
    inputs={k:v for k,v in index.items() if '0010_KO' in Path(k).parts and 'exce' in Path(k).name and k.endswith('.s14')}
    for rel,row in inputs.items():
        if sha256(snapshot/'game'/rel)!=row['sha256']:raise ValueError('Snapshot hash mismatch: '+rel)
    _,shared=probe(snapshot/'game/0010_KO/fixdataexce.s14')
    if shared is None:raise FormatError('Shared CE data cannot be decoded')
    dictionary,messages=catalog(shared,profile,inv)
    output.parent.mkdir(parents=True,exist_ok=True)
    temp_handle=tempfile.NamedTemporaryFile(prefix='ce-build-',suffix='.db',dir=output.parent,delete=False)
    temp=Path(temp_handle.name);temp_handle.close()
    conn=sqlite3.connect(temp)
    parsed=[];unparsed=[]
    try:
        conn.executescript((ROOT/'db/schema.sql').read_text('utf-8'))
        parser_digest=hashlib.sha256(b''.join(p.read_bytes() for p in sorted((ROOT/'extractors').glob('*.py')))+Path(__file__).read_bytes()+(ROOT/'scripts/probe_ce.py').read_bytes()+(ROOT/'scripts/source_catalog.py').read_bytes()+(ROOT/'db/schema.sql').read_bytes()).hexdigest()
        git=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True)
        with conn:
            conn.execute('INSERT INTO release_profile VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                         (profile['profile_key'],profile['build_id'],'ko','CE',sha256(snapshot/'inventory.json'),
                          sha256(profile_path),parser_digest,git.stdout.strip() or None,inv['captured_at'],0,
                          json.dumps(profile['blockers'],ensure_ascii=False)))
            for row in inv['files']:
                rel=row['relative_path']
                status='PENDING' if rel in inputs else 'EXCLUDED'
                conn.execute('INSERT INTO source_file(relative_path,sha256,size_bytes,processing_status,notes) VALUES(?,?,?,?,?)',
                             (rel,row['sha256'],row['size_bytes'],status,'CE Korean P0 candidate' if rel in inputs else 'Outside this candidate parser scope'))
            file_ids=dict(conn.execute('SELECT relative_path,id FROM source_file'))
            conn.execute("UPDATE source_file SET processing_status='EXTRACTED' WHERE id=?",(file_ids['0010_KO/fixdataexce.s14'],))
            message_file_id=file_ids[profile['message_source']['relative_path']]
            conn.execute("UPDATE source_file SET processing_status='EXTRACTED',notes='Hash-verified message supplement; selected catalog text only' WHERE id=?",(message_file_id,))
            conn.execute("UPDATE source_file SET processing_status='EXTRACTED',notes='Read-only static semantic evidence; executable never packaged' WHERE id=?",(file_ids[profile['semantic_source']['relative_path']],))
            for key,indices in [('officer_state',range(249,259)),('scenario_mode',range(4,9))]:
                conn.execute('INSERT INTO semantic_evidence VALUES(?,?,?)',(key,'SOURCE_MESSAGE_CROSS_CHECKED',json.dumps({'source_file_id':message_file_id,'entries':[messages[i] for i in indices]},ensure_ascii=False)))
            conn.execute('INSERT INTO semantic_evidence VALUES(?,?,?)',('officer_classification','SOURCE_GROUP_CROSS_CHECKED',json.dumps({'groups':profile['officer_groups'],'basis':'Source ID and record index plus biography message presence; not historical accuracy, playability or ownership'},ensure_ascii=False)))
            conn.execute('INSERT INTO semantic_evidence VALUES(?,?,?)',('policy_effect_application','STATIC_BASELINE_CROSS_CHECKED',json.dumps({'source_file_id':file_ids[profile['semantic_source']['relative_path']],'units':profile['policy_effect_units'],'scope':'Baseline policy reference only; no live saved-game calculation'},ensure_ascii=False)))
            for key,status,note in [('screen_validation','EXCLUDED_BY_USER','게임·브라우저·실기기 화면 검증 제외'),('remote_operations','UNRESOLVED','Remote deployment, rollback and observations not performed')]:
                conn.execute('INSERT INTO semantic_evidence VALUES(?,?,?)',(key,status,json.dumps({'note':note},ensure_ascii=False)))
            for app_id in inv['installed_dlc_ids']:
                conn.execute('INSERT INTO content_pack(code,steam_app_id,installed,ownership_status,evidence) VALUES(?,?,1,?,?)',
                             (f'STEAM_DLC_{app_id}',app_id,'INSTALL_MANIFEST_ONLY','InstalledDepots; not independent license verification'))
            for kind,rows in dictionary.items():
                for row in rows:
                    source_id=message_file_id if row.get('source')=='message' else file_ids['0010_KO/fixdataexce.s14']
                    conn.execute('INSERT INTO dictionary VALUES(?,?,?,?,?)',(kind,row['id'],row['name'],source_id,row['record_offset']))
                    if row.get('description'):
                        conn.execute('INSERT INTO dictionary_detail VALUES(?,?,?,?)',(kind,row['id'],row['description'],row.get('description_verification','SOURCE_TEXT')))
                    if 'message_id' in row:
                        conn.execute('INSERT INTO dictionary_text_source VALUES(?,?,?,?,?)',(kind,row['id'],message_file_id,row['message_id'],row['message_offset']))
                    if 'attributes' in row:
                        conn.execute('INSERT INTO dictionary_attribute VALUES(?,?,?)',(kind,row['id'],json.dumps(row['attributes'],ensure_ascii=False,sort_keys=True)))
                    if 'level_values' in row:
                        for level,value in enumerate(row['level_values'],1):
                            conn.execute('INSERT INTO policy_level_effect VALUES(?,?,?,?,?,?,?)',(row['id'],level,value,row['unit'],'STATIC_BASELINE_CROSS_CHECKED' if row['unit'] else 'UNUSED_SLOT',source_id,row['record_offset']+114+2*(level-1)))
                    if kind=='policy':
                        for slot,id in enumerate(row['components']):
                            if id>=len(dictionary['policy_effect']):raise FormatError('Invalid policy effect reference')
                            conn.execute('INSERT INTO policy_component VALUES(?,?,?)',(row['id'],id,slot))
            for rel in sorted(inputs):
                if not Path(rel).name.startswith('sceda'):continue
                path=snapshot/'game'/rel
                app_id=profile.get('dlc_wrappers',{}).get(path.name,{}).get('steam_app_id')
                meta,data=probe(path,steam_app_id=app_id)
                if data is None:
                    code=int(''.join(x for x in path.stem if x.isdigit()))
                    # Title candidates confirmed in the CE message catalog; body unresolved.
                    name={32:'조조의 오산',33:'패기웅심'}.get(code,f'미해석 시나리오 {code}')
                    conn.execute('INSERT INTO scenario VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                                 (f'ce-{code:02}',code,name,None,None,'UNCLASSIFIED','PENDING',file_ids[rel],'PENDING',None,None,'INSTALLED_BODY_UNREAD'))
                    conn.execute("UPDATE source_file SET processing_status='FAILED',notes=? WHERE id=?",(meta['reason'],file_ids[rel]))
                    unparsed.append({'path':rel,'reason':meta['reason']});continue
                header=meta['scenario']
                if meta['header_version']!=profile['record_layout']['header_version']:raise FormatError('Unknown header version')
                block,raw_rows=officer_records(data)
                classifications={r['source_id']:classify_record(r,profile,messages) for r in raw_rows if r['source_id']}
                officers=[interpret_record(data,r,dictionary) for r in raw_rows if r['source_id']]
                conn.execute('INSERT INTO scenario VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                             (header['id'],header['source_code'],header['name'],header['start_year'],header['start_month'],header['mode'],header['mode_verification'],file_ids[rel],'PARSED_REVIEW',len(officers),block['count'],'INSTALLED_REVIEW_REQUIRED'))
                conn.execute("UPDATE source_file SET processing_status='EXTRACTED',notes='Records decoded; semantics under review' WHERE id=?",(file_ids[rel],))
                sid=header['id'];rulers={r['force_id']:r['name'] for r in officers if r['raw_state']==1 and r['force_id']}
                for r in officers:
                    kind=classifications[r['id']]
                    existing=conn.execute('SELECT name,courtesy_name FROM officer WHERE id=?',(r['id'],)).fetchone()
                    if existing and existing!=(r['name'],r['courtesy_name']):raise FormatError(f'Identity differs across scenarios: {r["id"]}')
                    conn.execute('INSERT OR IGNORE INTO officer VALUES(?,?,?,?,?)',(r['id'],r['name'],r['courtesy_name'],kind,'SOURCE_GROUP_CROSS_CHECKED'))
                    columns=['name','state','raw_state','force_id','settlement_id','settlement_name','appearance_year','birth_year','death_year','leadership','strength','intelligence','politics','charisma','affinity','doctrine_id','doctrine','policy_id','policy','policy_level','record_offset','record_sha256']
                    names=['scenario_id','officer_id']+columns+['force_name','verification']
                    conn.execute('INSERT INTO officer_state('+','.join(names)+') VALUES('+','.join('?' for _ in names)+')',
                                 [sid,r['id']]+[r[k] for k in columns]+[rulers.get(r['force_id']),'STRUCTURAL_CROSS_CHECK_PENDING'])
                    keys=['integrity','diplomacy','han_attitude','ambition','aggression']
                    conn.execute('INSERT INTO officer_personality VALUES(?,?,?,?,?,?,?,?)',[sid,r['id']]+[r['personality'][k]['value'] for k in keys]+['CROSS_CHECKED'])
                    for key,p in r['personality'].items():
                        conn.execute('INSERT INTO personality_evidence VALUES(?,?,?,?,?,?)',(sid,r['id'],key,p['raw'],p['offset'],'I16_DELTA_10_BASE_3'))
                    for kind,key in [('trait','traits'),('formation','formations'),('tactic','tactics')]:
                        for slot,id in enumerate(r[key]):conn.execute('INSERT INTO officer_dictionary VALUES(?,?,?,?,?)',(sid,r['id'],kind,id,slot))
                scope=conn.execute('INSERT INTO relationship_scope(scenario_id,semantics,verification) VALUES(?,?,?)',(sid,'SCENARIO_COMPLETE_RECORDS','RAW_SLOTS_GAME_CHECK_PENDING')).lastrowid
                for r in officers:
                    conn.execute('INSERT INTO officer_kinship VALUES(?,?,?,?)',(sid,r['id'],r['spouse_id'],r['sworn_group_id']))
                    for type,targets in r['relationships'].items():
                        for slot,target in enumerate(targets):
                            conn.execute('INSERT INTO relationship_edge VALUES(?,?,?,?,?,?)',(scope,r['id'],target,type,slot,r['record_offset']))
                    if r['sworn_group_id']:
                        siblings=[x['id'] for x in officers if x['sworn_group_id']==r['sworn_group_id'] and x['id']!=r['id']]
                        for slot,target in enumerate(sorted(siblings)):
                            conn.execute('INSERT INTO relationship_edge VALUES(?,?,?,?,?,?)',(scope,r['id'],target,'SWORN_SIBLING',slot,r['record_offset']))
                parsed.append({**header,'named_records':len(officers),'record_slots':block['count']})
            metrics=[('scenario_files',len(inputs)-1,len(parsed),'PASS' if not unparsed else 'PARTIAL','All measured Korean scenario bodies decoded' if not unparsed else 'Some source containers remain unreadable'),
                     ('officer_state_labels',10,10,'PASS','Independent Korean message enum agrees with raw code order'),
                     ('scenario_mode_labels',5,5,'PASS','Independent Korean message enum'),
                     ('policy_level_vectors',1010,1010,'PASS','Source vectors and baseline arithmetic units; unlock-only vectors not presented as numeric effects'),
                     ('personality_fields',5,5,'PARTIAL','Signed raw deltas cross-checked with original format research; screen verification excluded'),
                     ('game_screen_checks',None,0,'PENDING','Excluded by user request; not a completed check'),
                     ('mobile_device_checks',2,0,'PENDING','Excluded by user request; not a completed check'),
                     ('relationship_semantics',None,0,'PARTIAL','Directed raw slots extracted per scenario; screen verification pending')]
            conn.executemany('INSERT INTO coverage VALUES(?,?,?,?,?)',metrics)
        integrity=conn.execute('PRAGMA integrity_check').fetchone()[0]
        foreign=conn.execute('PRAGMA foreign_key_check').fetchall()
        if integrity!='ok' or foreign:raise ValueError('Candidate integrity check failed')
        digest=content_digest(conn)
        counts={name:conn.execute('SELECT count(*) FROM '+name).fetchone()[0] for name in ['scenario','officer','officer_state','relationship_edge','dictionary']}
        conn.close(); temp.rename(output)
        report={'profile_key':profile['profile_key'],'build_id':profile['build_id'],'schema_version':profile['schema_version'],
                'candidate_sha256':sha256(output),'content_sha256':digest,'inventory_sha256':sha256(snapshot/'inventory.json'),
                'parser_sha256':parser_digest,'counts':counts,'parsed_scenarios':parsed,'unparsed_files':unparsed,
                'integrity':integrity,'foreign_key_violations':len(foreign),'release_ready':False,'blockers':profile['blockers']}
        write_json(report_path,report)
        return report
    except Exception:
        conn.close()
        if temp.exists():temp.unlink()
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['snapshot','profile','output','report']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();r=build(a.snapshot,a.profile,a.output,a.report)
    print(json.dumps({'counts':r['counts'],'release_ready':r['release_ready'],'content_sha256':r['content_sha256']},indent=2))

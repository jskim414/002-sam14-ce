"""Compare every candidate record and directional edge with its fixed snapshot.

This detects ETL loss/corruption, not semantic correctness of the measured layout.
"""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import sha256,write_json
from probe_ce import probe,officer_records
from extractors.ce import dictionaries,interpret_record

def verify(database,snapshot,profile_path):
    profile=json.loads(profile_path.read_text('utf-8'))
    inventory=json.loads((snapshot/'inventory.json').read_text('utf-8'))
    index={r['relative_path']:r for r in inventory['files']}
    def source(rel):
        path=snapshot/'game'/rel
        if sha256(path)!=index[rel]['sha256']:raise ValueError('Source hash mismatch: '+rel)
        return probe(path)[1]
    dictionary=dictionaries(source('0010_KO/fixdataexce.s14'),profile)
    c=sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
    issues=[];checks=[];row_count=0;edge_count=0
    try:
        release=c.execute('SELECT * FROM release_profile').fetchone()
        if release['inventory_sha256']!=sha256(snapshot/'inventory.json'):issues.append('Inventory lineage mismatch')
        if release['profile_sha256']!=sha256(profile_path):issues.append('Profile lineage mismatch')
        expected_dictionary={(kind,r['id'],r['name'],r['record_offset']) for kind,rows in dictionary.items() for r in rows}
        if expected_dictionary!={tuple(r) for r in c.execute('SELECT kind,id,name,record_offset FROM dictionary')}:issues.append('Dictionary source mismatch')
        expected_details={(kind,r['id'],r['description'],'SOURCE_TEXT') for kind,rows in dictionary.items() for r in rows if r.get('description')}
        if expected_details!={tuple(r) for r in c.execute('SELECT * FROM dictionary_detail')}:issues.append('Dictionary descriptions mismatch')
        components={(r['id'],id,slot) for r in dictionary['policy'] for slot,id in enumerate(r['components'])}
        if components!={tuple(r) for r in c.execute('SELECT * FROM policy_component')}:issues.append('Policy components mismatch')
        for s in c.execute("SELECT s.id,f.relative_path FROM scenario s JOIN source_file f ON f.id=s.source_file_id WHERE s.status='PARSED_REVIEW' ORDER BY s.id"):
            data=source(s['relative_path']);block,raw=officer_records(data)
            source_rows=[interpret_record(data,r,dictionary) for r in raw if r['source_id']]
            expected={r['id']:r for r in source_rows}
            actual={r['officer_id']:dict(r) for r in c.execute('SELECT * FROM officer_state WHERE scenario_id=?',(s['id'],))}
            local=[]
            if len(source_rows)!=len(expected):local.append('Duplicate source IDs')
            if set(expected)!=set(actual):local.append('ID sets differ')
            edges=set();attachments=set()
            for id,r in expected.items():
                if id not in actual:continue
                for key,value in r.items():
                    if key in ('id','courtesy_name','relationships','traits','formations','tactics','personality','spouse_id','sworn_group_id'):continue
                    if actual[id][key]!=value:local.append(f'{id}:{key}')
                identity=c.execute('SELECT name,courtesy_name FROM officer WHERE id=?',(id,)).fetchone()
                if tuple(identity)!=(r['name'],r['courtesy_name']):local.append(f'{id}:identity')
                for kind in ('trait','formation','tactic'):
                    for slot,target in enumerate(r[kind+'s']):attachments.add((id,kind,target,slot))
                personality=c.execute('SELECT * FROM officer_personality WHERE scenario_id=? AND officer_id=?',(s['id'],id)).fetchone()
                for key,item in r['personality'].items():
                    if personality[key]!=item['value']:local.append(f'{id}:personality:{key}')
                    evidence=c.execute('SELECT raw_value,record_offset,encoding FROM personality_evidence WHERE scenario_id=? AND officer_id=? AND field=?',(s['id'],id,key)).fetchone()
                    if evidence is None or tuple(evidence)!=(item['raw'],item['offset'],'I16_DELTA_10_BASE_3'):local.append(f'{id}:evidence:{key}')
                kin=c.execute('SELECT spouse_id,sworn_group_id FROM officer_kinship WHERE scenario_id=? AND officer_id=?',(s['id'],id)).fetchone()
                if tuple(kin)!=(r['spouse_id'],r['sworn_group_id']):local.append(f'{id}:kinship')
                for kind,targets in r['relationships'].items():
                    for slot,target in enumerate(targets):edges.add((id,target,kind,slot,r['record_offset']))
                if r['sworn_group_id']:
                    siblings=sorted(x['id'] for x in expected.values() if x['sworn_group_id']==r['sworn_group_id'] and x['id']!=id)
                    for slot,target in enumerate(siblings):edges.add((id,target,'SWORN_SIBLING',slot,r['record_offset']))
            actual_edges={tuple(r) for r in c.execute('SELECT e.from_officer_id,e.to_officer_id,e.type,e.slot,e.record_offset FROM relationship_edge e JOIN relationship_scope s ON s.id=e.scope_id WHERE s.scenario_id=?',(s['id'],))}
            actual_attachments={tuple(r) for r in c.execute('SELECT officer_id,kind,dictionary_id,slot FROM officer_dictionary WHERE scenario_id=?',(s['id'],))}
            if edges!=actual_edges:local.append('Directional edge sets differ')
            if attachments!=actual_attachments:local.append('Trait/formation slot sets differ')
            checks.append({'scenario_id':s['id'],'ids':len(expected),'edges':len(edges),'record_slots':block['count'],'pass':not local,'mismatches':local})
            issues.extend(f'{s["id"]}:{x}' for x in local);row_count+=len(expected);edge_count+=len(edges)
        return {'database_sha256':sha256(database),'pass':not issues,'records_checked':row_count,'edges_checked':edge_count,
                'limitation':'ETL equality only; shared layout hypotheses still require game-screen verification',
                'scenarios':checks,'issues':issues}
    finally:c.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['database','snapshot','profile','report']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();r=verify(a.database,a.snapshot,a.profile);write_json(a.report,r)
    print(json.dumps({k:v for k,v in r.items() if k not in ('scenarios','issues')},indent=2))
    raise SystemExit(0 if r['pass'] else 2)

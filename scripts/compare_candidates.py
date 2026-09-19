"""Check changes against the immutable r3 baseline, preserving scenario IDs."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
from contextlib import closing
from common import sha256, write_json


def compare(old,new):
    with closing(sqlite3.connect(old.resolve().as_uri()+'?mode=ro',uri=True)) as a, closing(sqlite3.connect(new.resolve().as_uri()+'?mode=ro',uri=True)) as b:
        a.row_factory=b.row_factory=sqlite3.Row
        before={r['id']:dict(r) for r in a.execute('SELECT * FROM scenario')}
        after={r['id']:dict(r) for r in b.execute('SELECT * FROM scenario')}
        changed=Counter();unexpected=[];rows=0
        for sid in before:
            if before[sid]['status']!='PARSED_REVIEW':continue
            old_rows={r['officer_id']:dict(r) for r in a.execute('SELECT * FROM officer_state WHERE scenario_id=?',(sid,))}
            new_rows={r['officer_id']:dict(r) for r in b.execute('SELECT * FROM officer_state WHERE scenario_id=?',(sid,))}
            if old_rows.keys()!=new_rows.keys():unexpected.append(sid+':id sets')
            for id,row in old_rows.items():
                if id not in new_rows:continue
                rows+=1
                for field,value in row.items():
                    updated=new_rows[id][field]
                    if value!=updated:
                        changed[field]+=1
                        if field!='state' or (value,updated) not in [('UNVERIFIED_STATUS','FREE'),('FREE','UNDISCOVERED'),('DEAD_OR_RETIRED','DEAD')]:
                            unexpected.append(f'{sid}:{id}:{field}')
            sql='SELECT e.from_officer_id,e.to_officer_id,e.type,e.slot,e.record_offset FROM relationship_edge e JOIN relationship_scope r ON r.id=e.scope_id WHERE r.scenario_id=?'
            if {tuple(x) for x in a.execute(sql,(sid,))}!={tuple(x) for x in b.execute(sql,(sid,))}:unexpected.append(sid+':relationships')
        return {'baseline_sha256':sha256(old),'candidate_sha256':sha256(new),'pass':not unexpected,
                'existing_records_compared':rows,'changed_fields':dict(changed),'unexpected_changes':unexpected,
                'newly_decoded':[sid for sid in after if after[sid]['status']=='PARSED_REVIEW' and before.get(sid,{}).get('status')!='PARSED_REVIEW']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('baseline','candidate','report'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();r=compare(a.baseline,a.candidate);write_json(a.report,r);print(json.dumps(r,indent=2));raise SystemExit(0 if r['pass'] else 2)

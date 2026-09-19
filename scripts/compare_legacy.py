"""Read-only comparison hints; never turn Legacy name matches into CE identities."""
import argparse
from collections import defaultdict,Counter
from pathlib import Path
import sqlite3
from common import sha256,write_json

def compare(legacy,candidate):
    connections=[]
    try:
        for path in (legacy,candidate):
            c=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;connections.append(c)
        old,new=connections
        names=defaultdict(list)
        for r in old.execute("SELECT * FROM v_officer_search WHERE ruleset='PK'"):names[r['name_ko']].append(dict(r))
        new_names=Counter(r[0] for r in new.execute('SELECT name FROM officer'))
        details=[]
        fields=['leadership','strength','intelligence','politics','charisma','affinity','doctrine','policy','policy_level']
        for r in new.execute("SELECT s.*,o.kind FROM officer_state s JOIN officer o ON o.id=s.officer_id WHERE scenario_id='ce-05' ORDER BY officer_id"):
            matches=names[r['name']]
            item={'ce_source_id':r['officer_id'],'name':r['name'],'ce_kind':r['kind'],'mapping_authorized':False}
            if not matches:item['classification']='NO_LEGACY_NAME_MATCH'
            elif len(matches)!=1 or new_names[r['name']]!=1:item['classification']='AMBIGUOUS_NAME'
            else:
                match=matches[0];changes={key:{'legacy':match[key],'ce':r[key]} for key in fields if match[key]!=r[key]}
                item.update(legacy_internal_id=match['internal_id'],id_equal=match['internal_id']==r['officer_id'],changes=changes,
                            classification='UNIQUE_NAME_REVIEW_CHANGED' if changes else 'UNIQUE_NAME_REVIEW_EQUAL',
                            reason='Potential CE revision, Legacy error, or mistaken identity; unresolved until independent evidence')
            details.append(item)
        return {'legacy_sha256':sha256(legacy),'candidate_sha256':sha256(candidate),'ce_scenario':'ce-05',
                'status':'REVIEW_HINTS_ONLY','counts':dict(Counter(x['classification'] for x in details)),
                'id_mismatches':sum(x.get('id_equal') is False for x in details),
                'not_comparable':['Legacy relationships have different source/scope','Personality is not verified','Other scenario states are not equated by scenario number'],
                'officers':details}
    finally:
        for c in connections:c.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['legacy','candidate','output']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();r=compare(a.legacy,a.candidate);write_json(a.output,r);print(r['counts']);print('ID mismatches:',r['id_mismatches'])

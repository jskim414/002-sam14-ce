"""Reproduce DLC wrapper/header verification using private KO/JP snapshots."""
import argparse
import json
from pathlib import Path
from common import sha256, write_json
from probe_ce import probe, officer_records


def analyze(snapshot, profile_path):
    inventory=json.loads((snapshot/'inventory.json').read_text('utf-8'))
    profile=json.loads(profile_path.read_text('utf-8'))
    files=[]
    for source in inventory['files']:
        rel=Path(source['relative_path'])
        if rel.name not in profile['dlc_wrappers'] or rel.parent.name not in ('0010_KO','0010_JP'):continue
        path=snapshot/'game'/rel
        if sha256(path)!=source['sha256']:raise ValueError('DLC snapshot changed')
        app=profile['dlc_wrappers'][rel.name]['steam_app_id']
        meta,body=probe(path,steam_app_id=app)
        if body is None:raise ValueError(meta['reason'])
        entry={k:v for k,v in meta.items() if k!='title_candidate'}
        entry.update(relative_path=rel.as_posix(),steam_app_id=app)
        if rel.parent.name=='0010_KO':
            block,rows=officer_records(body);ids=[r['source_id'] for r in rows if r['source_id']]
            if len(ids)!=len(set(ids)):raise ValueError('Duplicate officer IDs')
            entry.update(officer_block=block,nonzero_ids=len(ids),duplicate_ids=0)
        files.append(entry)
    if len(files)!=4:raise ValueError('Expected both Korean and Japanese DLC sources')
    for code in (32,33):
        pair=[r['scenario'] for r in files if r['scenario']['source_code']==code]
        if len(pair)!=2 or any(pair[0][k]!=pair[1][k] for k in ('start_year','start_month','mode')):
            raise ValueError('KO/JP header disagreement')
    return {'pass':True,'build_id':inventory['steam_build_id'],'inventory_sha256':sha256(snapshot/'inventory.json'),
            'method':'DLC_LCG_XOR_V1 -> SN14SCEXVER0001 -> LWC',
            'seed':'(scenario_code + Steam DLC app id) modulo 2^32',
            'step':'state = state * 0x6c078965 + 0x3039 modulo 2^32; XOR byte = ((state >> 16) XOR (state >> 24)) AND 255',
            'files':files,'scope':'Read-only installed data analysis; no game patch, no game execution, no entitlement claim',
            'screen_validation':'EXCLUDED_BY_USER'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('snapshot','profile','report'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();result=analyze(a.snapshot,a.profile);write_json(a.report,result)
    print(json.dumps({'pass':result['pass'],'files':len(result['files'])}))

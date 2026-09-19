"""Bind automatic validation evidence to one immutable local candidate."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from common import sha256,write_json
from run_checks import suite_digest
from validate_db import validate


def assess(database,source,tests,diff,rebuild):
    identity=sha256(database)
    reports={key:json.loads(path.read_text('utf-8')) for key,path in [('source',source),('tests',tests),('diff',diff),('rebuild',rebuild)]}
    with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True)) as c:
        records=c.execute('SELECT count(*) FROM officer_state').fetchone()[0]
        edges=c.execute('SELECT count(*) FROM relationship_edge').fetchone()[0]
        git=c.execute('SELECT git_sha FROM release_profile').fetchone()[0]
    checks={}
    for key,data in reports.items():
        checks[key+'_identity']=data.get('candidate_sha256' if key=='diff' else 'database_sha256')==identity
    checks['source_all_records']=reports['source'].get('pass') is True and reports['source'].get('records_checked')==records and reports['source'].get('edges_checked')==edges
    test=reports['tests']
    checks['real_integration']=test.get('pass') is True and test.get('mode')=='REAL_INTEGRATION' and test.get('python',{}).get('skipped')==[] and test.get('git_sha')==git and test.get('test_suite_sha256')==suite_digest()
    checks['baseline_diff']=reports['diff'].get('pass') is True
    checks['reproducibility']=reports['rebuild'].get('rebuild_sha256')==identity and reports['rebuild'].get('byte_identical') is True
    structural=validate(database);checks['structural']=structural['structural_pass']
    return {'database_sha256':identity,'git_sha':git,'local_review_ready':all(checks.values()),
            'checks':checks,'publication_ready':structural['release_ready'],
            'screen_validation':'EXCLUDED_BY_USER','remote_deployment':'NOT_PERFORMED',
            'evidence_files':{key:{'path':path.as_posix(),'sha256':sha256(path)} for key,path in [('source',source),('tests',tests),('diff',diff),('rebuild',rebuild)]}}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('database','source','tests','diff','rebuild','report'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();r=assess(a.database,a.source,a.tests,a.diff,a.rebuild);write_json(a.report,r)
    print(json.dumps({'local_review_ready':r['local_review_ready'],'publication_ready':r['publication_ready'],'checks':r['checks']},indent=2))
    raise SystemExit(0 if r['local_review_ready'] else 2)

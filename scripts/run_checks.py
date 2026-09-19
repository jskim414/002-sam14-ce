"""Run portable contracts; --database requires every real integration test."""
import argparse
import hashlib
import io
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import unittest
from common import ROOT,sha256,write_json


def suite_digest():
    return hashlib.sha256(b''.join(p.read_bytes() for p in sorted((ROOT/'tests').glob('*')) if p.is_file())).hexdigest()


def run(database=None):
    if database:
        database=database.resolve(strict=True)
        os.environ['CE_TEST_DATABASE']=str(database)
    else:os.environ.pop('CE_TEST_DATABASE',None)
    sys.path.insert(0,str(ROOT))
    log=io.StringIO()
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    result=unittest.TextTestRunner(stream=log,verbosity=1).run(suite)
    npm=shutil.which('npm')
    if not npm:raise RuntimeError('npm is required for DOM contracts')
    js=subprocess.run([npm,'test'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
    syntax=subprocess.run([npm,'run','check'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
    report={'pass':result.wasSuccessful() and js.returncode==0 and syntax.returncode==0 and (not database or not result.skipped),
            'mode':'REAL_INTEGRATION' if database else 'SYNTHETIC_CONTRACTS',
            'database_sha256':sha256(database) if database else None,
            'test_suite_sha256':suite_digest(),'python_version':platform.python_version(),
            'python':{'run':result.testsRun,'passed':result.testsRun-len(result.skipped)-len(result.failures)-len(result.errors),
                      'failures':len(result.failures),'errors':len(result.errors),'skipped':[{'id':str(t),'reason':reason} for t,reason in result.skipped]},
            'javascript_exit_code':js.returncode,'syntax_exit_code':syntax.returncode,
            'screen_validation':'EXCLUDED_BY_USER'}
    report['git_sha']=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    if not report['pass']:print(log.getvalue()+js.stdout+js.stderr+syntax.stderr,file=sys.stderr)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--database',type=Path);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    r=run(a.database);write_json(a.report,r);print(f"Checks passed: {r['pass']}; Python: {r['python']['passed']}/{r['python']['run']}; mode: {r['mode']}")
    raise SystemExit(0 if r['pass'] else 2)

"""Standalone allowlist/hash verification, copied into each release package."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from contextlib import closing
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1] if Path(__file__).parent.name=='scripts' else Path(__file__).resolve().parent))
from web.release_gate import evaluate

BASE_FILES={'api/index.py','web/queries.py','web/server.py','web/release_gate.py','vercel.json',
            'check_package.py','.python-version','requirements.txt','run.py'}
REVIEW_FILES={'db/sam14.db'}|{'web/static/'+name for name in ('index.html','styles.css','app.js','state.mjs',
               'vendor/qrcode.mjs','vendor/qrcode-LICENSE.txt','vendor/qrcode-provenance.json')}

def verify(root,release=False,deploy=False):
    root=root.resolve();manifest=json.loads((root/'package-manifest.json').read_text('utf-8'))
    files=manifest['files']
    if manifest.get('mode') not in ('maintenance','review','public-review','release'):raise ValueError('Invalid package mode')
    if deploy and manifest['mode']=='review':raise ValueError('Local review package cannot be deployed')
    if deploy and manifest['mode']=='release':release=True
    version=manifest.get('format_version',1)
    if version not in (1,2):raise ValueError('Unsupported package format version')
    base=BASE_FILES if version==2 else BASE_FILES-{'web/release_gate.py'}
    allowed=base if manifest['mode']=='maintenance' else base|REVIEW_FILES
    if set(files)!=allowed:raise ValueError('Unexpected or missing allowlisted package files')
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and '.vercel' not in p.parts}
    # Vercel's Python installer creates this empty lock before the build command.
    if os.environ.get('VERCEL')=='1':actual.discard('.vercel_python_packages/.lock')
    expected=set(files)|{'package-manifest.json'}
    if actual!=expected:raise ValueError(f'Unexpected or missing package files: unexpected={sorted(actual-expected)}, missing={sorted(expected-actual)}')
    for rel,evidence in files.items():
        path=(root/rel).resolve(strict=True)
        if rel=='vercel.json' and os.environ.get('VERCEL')=='1' and path.is_relative_to(root) and manifest.get('vercel_config'):
            actual_config=json.loads(path.read_text('utf-8'))
            # The CLI injects deployment metadata and reformats this JSON.
            if 'name' not in manifest['vercel_config']:actual_config.pop('name',None)
            if 'version' not in manifest['vercel_config'] and actual_config.get('version')==2:actual_config.pop('version')
            if actual_config!=manifest['vercel_config']:raise ValueError('Vercel configuration changed: '+json.dumps(actual_config,sort_keys=True))
            continue
        if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest()!=evidence['sha256'] or path.stat().st_size!=evidence['bytes']:raise ValueError('Package content mismatch: '+rel)
    if manifest['mode']=='maintenance':return manifest
    if manifest.get('database_sha256')!=files['db/sam14.db']['sha256']:raise ValueError('Database manifest identity mismatch')
    with closing(sqlite3.connect((root/'db/sam14.db').as_uri()+'?mode=ro',uri=True)) as conn:
        ready=evaluate(conn)['release_ready']
        if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Database integrity failure')
    if release and (manifest['mode']!='release' or not ready):raise ValueError('Publication blocked: unresolved release gates')
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--release',action='store_true');p.add_argument('--deploy',action='store_true');a=p.parse_args()
    root=Path(__file__).resolve().parent
    m=verify(root,a.release,a.deploy)
    print(json.dumps({'verified':True,'mode':m['mode'],'files':len(m['files'])}))

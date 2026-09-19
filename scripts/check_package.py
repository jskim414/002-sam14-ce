"""Standalone allowlist/hash verification, copied into each release package."""
import argparse
import hashlib
import json
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

def verify(root,release=False):
    root=root.resolve();manifest=json.loads((root/'package-manifest.json').read_text('utf-8'))
    files=manifest['files']
    if manifest.get('mode') not in ('maintenance','review','release'):raise ValueError('Invalid package mode')
    version=manifest.get('format_version',1)
    if version not in (1,2):raise ValueError('Unsupported package format version')
    base=BASE_FILES if version==2 else BASE_FILES-{'web/release_gate.py'}
    allowed=base if manifest['mode']=='maintenance' else base|REVIEW_FILES
    if set(files)!=allowed:raise ValueError('Unexpected or missing allowlisted package files')
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and '.vercel' not in p.parts}
    if actual!=set(files)|{'package-manifest.json'}:raise ValueError('Unexpected or missing package files')
    for rel,evidence in files.items():
        path=(root/rel).resolve(strict=True)
        if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest()!=evidence['sha256'] or path.stat().st_size!=evidence['bytes']:raise ValueError('Package content mismatch: '+rel)
    if manifest['mode']=='maintenance':return manifest
    if manifest.get('database_sha256')!=files['db/sam14.db']['sha256']:raise ValueError('Database manifest identity mismatch')
    with closing(sqlite3.connect((root/'db/sam14.db').as_uri()+'?mode=ro',uri=True)) as conn:
        ready=evaluate(conn)['release_ready']
        if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Database integrity failure')
    if release and (manifest['mode']!='release' or not ready):raise ValueError('Publication blocked: unresolved release gates')
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--release',action='store_true');a=p.parse_args()
    m=verify(Path(__file__).resolve().parent,a.release)
    print(json.dumps({'verified':True,'mode':m['mode'],'files':len(m['files'])}))

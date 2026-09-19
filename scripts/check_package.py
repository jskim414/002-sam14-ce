"""Standalone allowlist/hash verification, copied into each release package."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

def verify(root,release=False):
    root=root.resolve();manifest=json.loads((root/'package-manifest.json').read_text('utf-8'))
    files=manifest['files']
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and '.vercel' not in p.parts}
    if actual!=set(files)|{'package-manifest.json'}:raise ValueError('Unexpected or missing package files')
    for rel,evidence in files.items():
        path=(root/rel).resolve(strict=True)
        if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest()!=evidence['sha256'] or path.stat().st_size!=evidence['bytes']:raise ValueError('Package content mismatch: '+rel)
    if manifest['mode']=='maintenance':return manifest
    with sqlite3.connect((root/'db/sam14.db').as_uri()+'?mode=ro',uri=True) as conn:
        ready,blockers=conn.execute('SELECT release_ready,blockers_json FROM release_profile').fetchone()
        if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Database integrity failure')
    if release and (manifest['mode']!='release' or not ready or json.loads(blockers)):raise ValueError('Publication blocked: unresolved release gates')
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--release',action='store_true');a=p.parse_args()
    m=verify(Path(__file__).resolve().parent,a.release)
    print(json.dumps({'verified':True,'mode':m['mode'],'files':len(m['files'])}))

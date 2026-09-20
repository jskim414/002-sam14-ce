"""Create a minimal, immutable CE release/review/maintenance package. Never deploy."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from common import ROOT,output_path,sha256,write_json
from validate_db import validate
from check_package import verify

def package(output,database=None,mode='release'):
    output=output_path(output)
    if not output.is_relative_to(ROOT/'.artifacts/packages'):raise ValueError('Package must be inside CE .artifacts/packages')
    if mode not in ('release','review','public-review','maintenance'):raise ValueError('Invalid package mode')
    if mode!='maintenance':
        if database is None:raise ValueError('Database required')
        database=database.resolve(strict=True)
        if not database.is_relative_to(ROOT):raise ValueError('Only an independent CE database may be packaged')
        result=validate(database)
        if not result['structural_pass'] or (mode=='release' and not result['release_ready']):raise ValueError('Release gate not satisfied; use --mode review for a local review package')
    output.mkdir(parents=True)
    selected=['api/index.py','web/queries.py','web/server.py','web/release_gate.py','vercel.json']
    if mode!='maintenance':selected += ['web/static/'+name for name in ('index.html','styles.css','app.js','state.mjs','vendor/qrcode.mjs','vendor/qrcode-LICENSE.txt','vendor/qrcode-provenance.json')]
    for rel in selected:
        src=(ROOT/rel).resolve(strict=True)
        if not src.is_relative_to(ROOT):raise ValueError('Source escapes CE project')
        dst=output/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
    shutil.copyfile(ROOT/'scripts/check_package.py',output/'check_package.py')
    if mode=='public-review':
        config=json.loads((output/'vercel.json').read_text('utf-8'))
        config['buildCommand']='python check_package.py --deploy'
        config['outputDirectory']='web/static'
        (output/'vercel.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
    (output/'.python-version').write_text('3.12\n',encoding='utf-8')
    (output/'requirements.txt').write_text('# Python standard library only\n',encoding='utf-8')
    if mode!='maintenance':
        (output/'db').mkdir();shutil.copyfile(database,output/'db/sam14.db')
    runner="""from pathlib import Path
from http.server import ThreadingHTTPServer
import argparse
from check_package import verify
root=Path(__file__).resolve().parent
manifest=verify(root)
p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8142);a=p.parse_args()
if manifest['mode']=='maintenance':
 from api.index import MaintenanceHandler
 server=ThreadingHTTPServer(('127.0.0.1',a.port),MaintenanceHandler)
else:
 from web.server import create_server
 server=create_server('127.0.0.1',a.port,root/'db/sam14.db')
print(f'http://127.0.0.1:{server.server_port}',flush=True)
server.serve_forever()
"""
    (output/'run.py').write_text(runner,encoding='utf-8')
    files={p.relative_to(output).as_posix():{'sha256':sha256(p),'bytes':p.stat().st_size} for p in sorted(output.rglob('*')) if p.is_file()}
    total=sum(x['bytes'] for x in files.values())
    if total>=450*1024*1024:raise ValueError('Package exceeds conservative 450 MiB budget')
    git=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True)
    manifest={'format_version':2,'mode':mode,'git_sha':git.stdout.strip() or None,'files':files,'total_bytes':total,'database_sha256':sha256(database) if mode!='maintenance' else None,'public_deployment_performed':False}
    manifest['vercel_config']=json.loads((output/'vercel.json').read_text('utf-8'))
    write_json(output/'package-manifest.json',manifest)
    verify(output,release=mode=='release')
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--database',type=Path);p.add_argument('--mode',choices=['release','review','public-review','maintenance'],default='release');a=p.parse_args()
    m=package(a.output,a.database,a.mode);print(json.dumps({k:v for k,v in m.items() if k!='files'},indent=2))

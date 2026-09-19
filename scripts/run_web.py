"""Run the CE candidate locally; public binding is intentionally disabled."""
import argparse
from pathlib import Path
import sys
import webbrowser
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from web.server import create_server

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database',type=Path,default=ROOT/'db/ce-24966116-r3.final.db')
    p.add_argument('--port',type=int,default=8141)
    p.add_argument('--no-browser',action='store_true')
    a=p.parse_args()
    database=a.database.resolve(strict=True)
    if not database.is_relative_to((ROOT/'db').resolve()):raise SystemExit('Only the independent CE db folder is allowed')
    server=create_server('127.0.0.1',a.port,database)
    print(f'CE local review: http://127.0.0.1:{a.port}',flush=True)
    if not a.no_browser:webbrowser.open(f'http://127.0.0.1:{a.port}')
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

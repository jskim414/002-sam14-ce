"""CE-only Vercel entrypoint; unapproved or missing data serves maintenance."""
from http.server import BaseHTTPRequestHandler
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from web.queries import Queries
from web.server import make_handler

class MaintenanceHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body=json.dumps({'status':'maintenance','message':'CE 데이터를 검증 중입니다. 잠시 후 다시 확인해 주세요.'},ensure_ascii=False).encode()
        self.send_response(503)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('Retry-After','3600')
        self.end_headers();self.wfile.write(body)

def public_review_authorized(root):
    """Only explicitly packaged review data may run before semantic release."""
    manifest=json.loads((root/'package-manifest.json').read_text('utf-8'))
    if manifest.get('mode')!='public-review':return False
    expected=manifest.get('database_sha256')
    if not expected or manifest['files']['db/sam14.db']['sha256']!=expected:return False
    digest=hashlib.sha256()
    with (root/'db/sam14.db').open('rb') as stream:
        for chunk in iter(lambda:stream.read(4*1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()==expected

def select_handler():
    if os.environ.get('CE_MAINTENANCE')=='1':return MaintenanceHandler
    try:
        service=Queries(ROOT/'db/sam14.db')
        coverage=service.coverage()
        if (not coverage['release_ready'] or coverage['blockers']) and not public_review_authorized(ROOT):return MaintenanceHandler
        return make_handler(service)
    except Exception:return MaintenanceHandler

handler=select_handler()

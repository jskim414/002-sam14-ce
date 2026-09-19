"""CE-only Vercel entrypoint; unapproved or missing data serves maintenance."""
from http.server import BaseHTTPRequestHandler
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

def select_handler():
    if os.environ.get('CE_MAINTENANCE')=='1':return MaintenanceHandler
    try:
        service=Queries(ROOT/'db/sam14.db')
        coverage=service.coverage()
        if not coverage['release_ready'] or coverage['blockers']:return MaintenanceHandler
        return make_handler(service)
    except Exception:return MaintenanceHandler

handler=select_handler()

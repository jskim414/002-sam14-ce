from __future__ import annotations
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
from urllib.parse import urlsplit,parse_qsl,unquote
from .queries import Queries, ValidationError, NotFound

STATIC=Path(__file__).resolve().parent/'static'

def make_handler(service):
    class Handler(BaseHTTPRequestHandler):
        def send(self,status,data,mime='application/json; charset=utf-8'):
            body=json.dumps(data,ensure_ascii=False).encode() if isinstance(data,(dict,list)) else data
            self.send_response(status);self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
            self.end_headers();self.wfile.write(body)

        def do_GET(self):
            try:
                url=urlsplit(self.path);pairs=parse_qsl(url.query,keep_blank_values=True)
                if len(pairs)>30 or len(dict(pairs))!=len(pairs):raise ValidationError('중복 또는 과도한 검색 조건입니다.')
                f=dict(pairs);path=unquote(url.path)
                if path.startswith('/api/'):
                    if path=='/api/v1/officers':return self.send(200,service.officers(f))
                    if path=='/api/v1/compare':
                        if set(f)-{'ids','scenario'}:raise ValidationError('지원하지 않는 비교 조건입니다.')
                        return self.send(200,service.compare(f.get('ids',''),f.get('scenario')))
                    match=re.fullmatch(r'/api/v1/officers/(\d+)(/relationships)?',path)
                    if match:
                        if set(f)-{'scenario'}:raise ValidationError('지원하지 않는 상세 조건입니다.')
                        call=service.relationships if match[2] else service.officer
                        return self.send(200,call(int(match[1]),f.get('scenario')))
                    if path=='/api/v1/forces':
                        if set(f)-{'scenario'}:raise ValidationError('지원하지 않는 조건입니다.')
                        return self.send(200,{'items':service.forces(f.get('scenario'))})
                    calls={'/api/v1/health':service.health,'/api/v1/meta':service.meta,
                           '/api/v1/coverage':service.coverage,'/api/v1/scenarios':lambda:{'items':service.scenarios()}}
                    if path in calls:
                        if f:raise ValidationError('이 API는 검색 조건을 받지 않습니다.')
                        return self.send(200,calls[path]())
                    dictionary_match=re.fullmatch(r'/api/v1/(traits|policies|formations|tactics|doctrines)(?:/(\d+))?',path)
                    if dictionary_match:
                        if f:raise ValidationError('이 도감 API는 검색 조건을 받지 않습니다.')
                        kind={'traits':'trait','policies':'policy','formations':'formation','tactics':'tactic','doctrines':'doctrine'}[dictionary_match[1]]
                        return self.send(200,service.codex(kind,int(dictionary_match[2]) if dictionary_match[2] else None))
                    raise NotFound('API를 찾을 수 없습니다.')
                if f and path!='/':raise NotFound('페이지를 찾을 수 없습니다.')
                rel='index.html' if path=='/' else path.lstrip('/')
                target=(STATIC/rel).resolve()
                if not target.is_relative_to(STATIC.resolve()) or not target.is_file():raise NotFound('페이지를 찾을 수 없습니다.')
                mime=mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
                if target.suffix in ('.js','.mjs'):mime='text/javascript'
                self.send(200,target.read_bytes(),mime+'; charset=utf-8')
            except ValidationError as e:self.send(400,{'error':str(e),'code':'INVALID_REQUEST'})
            except NotFound as e:self.send(404,{'error':str(e),'code':'NOT_FOUND'})
            except Exception:self.send(500,{'error':'데이터를 읽는 중 문제가 발생했습니다.','code':'INTERNAL_ERROR'})
    return Handler

def create_server(host,port,database):return ThreadingHTTPServer((host,port),make_handler(Queries(database)))

import json
from pathlib import Path
import sqlite3
import struct
import tempfile
import threading
import unittest
import zlib
from urllib.request import urlopen
from support import make_fixture
from extractors.messages import decode_zp1, string_table, STATE_CODES
from extractors.lwc import FormatError
from web.queries import Queries
from web.release_gate import evaluate
from web.server import create_server
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from assess_candidate import assess


def zp1(data):
    payload=zlib.compress(data)
    header=b'zp1\0'+struct.pack('<IIII',len(data),0x40000,1,len(payload)+4)
    return header.ljust(0x800,b'\0')+struct.pack('<I',len(payload))+payload


class MessageTests(unittest.TestCase):
    def test_roundtrip_and_corrupt_blocks(self):
        data=b'synthetic'*100
        raw=zp1(data)
        self.assertEqual(decode_zp1(raw),data)
        for bad in (raw[:-1],raw[:4]+struct.pack('<I',99_000_000)+raw[8:],raw[:0x800]+struct.pack('<I',1)+raw[0x804:]):
            with self.assertRaises(FormatError):decode_zp1(bad)
        with self.assertRaises(FormatError):decode_zp1(zp1(b''))
    def test_string_directory_and_bounds(self):
        strings=['합성','문자열','']
        payload=b'';offsets=[]
        for value in strings:
            offsets.append(len(strings)*4+len(payload));payload+=(value+'\0').encode('utf-16le')
        section=bytes(24)+struct.pack('<3I',*offsets)+payload
        directory=struct.pack('<I8I',4,36,len(section),36+len(section),0,36+len(section),0,36+len(section),0)
        data=struct.pack('<3I',1,12,len(directory)+len(section))+directory+section
        self.assertEqual([r['text'] for r in string_table(data)],strings)
        bad=bytearray(data);struct.pack_into('<I',bad,76,2)
        with self.assertRaises(FormatError):string_table(bad)
    def test_state_codes_distinguish_free_hidden_and_prisoner(self):
        self.assertEqual([STATE_CODES[i] for i in (5,6,7,8,9)],['FREE','PRISONER','UNAPPEARED','UNDISCOVERED','DEAD'])


class SyntheticApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.db=make_fixture(Path(self.temp.name)/'fixture.db');self.q=Queries(self.db)
    def tearDown(self):self.temp.cleanup()
    def test_catalog_numeric_zero_missing_unit_and_comparison(self):
        self.assertEqual(self.q.codex('scenic')['items'][0]['name'],'합성 명승')
        self.assertEqual(len(self.q.codex('policy',47)['items'][0]['level_effects'][0]['levels']),10)
        c=sqlite3.connect(self.db)
        with c:c.execute('UPDATE policy_level_effect SET raw_value=0 WHERE level=1')
        c.close()
        effect=self.q.codex('policy',47)['items'][0]['level_effects'][0]['levels'][0]
        self.assertEqual(effect['raw_value'],0);self.assertIsNone(effect['unit'])
        self.assertEqual([x['officer_id'] for x in self.q.compare('147,521')['items']],[147,521])
    def test_profile_flag_cannot_bypass_evidence(self):
        c=sqlite3.connect(self.db)
        with c:c.execute("UPDATE release_profile SET release_ready=1,blockers_json='[]'")
        self.assertFalse(evaluate(c)['release_ready']);c.close()
        self.assertFalse(self.q.health()['release_ready']);self.assertFalse(self.q.meta()['capabilities']['publication'])
        self.assertFalse(self.q.coverage()['release_ready'])
    def test_stale_or_missing_candidate_reports_fail_closed(self):
        paths=[]
        for name in ('source','tests','diff','rebuild'):
            path=Path(self.temp.name)/(name+'.json');path.write_text(json.dumps({'pass':True,'database_sha256':'f'*64}),encoding='utf-8');paths.append(path)
        result=assess(self.db,*paths)
        self.assertFalse(result['local_review_ready']);self.assertFalse(result['publication_ready'])
        self.assertFalse(result['checks']['source_identity']);self.assertFalse(result['checks']['real_integration'])
    def test_http_catalog_and_both_dlc_contracts(self):
        server=create_server('127.0.0.1',0,self.db);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            for path in ('health','meta','scenics','strategies','literatures','merits','policies/47','officers?scenario=ce-32','officers?scenario=ce-33'):
                with urlopen(f'http://127.0.0.1:{server.server_port}/api/v1/{path}') as r:self.assertEqual(r.status,200)
        finally:server.shutdown();server.server_close();thread.join()

import json
from pathlib import Path
import sqlite3
import struct
import sys
import tempfile
import threading
import unittest
from urllib.request import urlopen
from urllib.error import HTTPError
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from extractors.lwc import decode,FormatError
from common import output_path,LEGACY,ROOT
from diff_install_inventory import compare
from web.queries import Queries,ValidationError
from web.server import create_server
from validate_db import validate

def stream(size,payload):return b'LWC\x1a'+struct.pack('<II',size,len(payload))+bytes(range(256))+payload

class LwcTests(unittest.TestCase):
    def test_known_literal_vector(self):
        # Codes 0,1,2: 00 01 1000; padding is already byte-aligned.
        self.assertEqual(decode(stream(3,b'\x18')),b'\0\1\2')
    def test_bad_header_size_and_table(self):
        for data in [b'bad',stream(100,b''),stream(99_000_000,b'\0'),stream(1,b'\0')+b'x']:
            with self.assertRaises(FormatError):decode(data)
    def test_backreference_without_history(self):
        # code 257: prefix 11111110 + payload 00000011.
        with self.assertRaises(FormatError):decode(stream(4,b'\xfe\x03\x00'))
    def test_overlapping_backreference(self):
        # Literal zero + distance one (code 257) + count four (code 1).
        bits='00'+'11111110'+'00000011'+'01'
        payload=int(bits.ljust(24,'0'),2).to_bytes(3,'big')
        self.assertEqual(decode(stream(5,payload)),bytes(5))

class BoundaryTests(unittest.TestCase):
    def test_outputs_cannot_touch_legacy(self):
        for path in [LEGACY/'db/new.db',ROOT.parent/'escape.db',ROOT/'db/sam14.db',ROOT/'.git/config']:
            with self.assertRaises((ValueError,FileExistsError)):output_path(path)
    def test_no_overwrite(self):
        with self.assertRaises(FileExistsError):output_path(ROOT/'README.md' if (ROOT/'README.md').exists() else ROOT/'db/schema.sql')
    def test_inventory_diff_all_states(self):
        a={'files':[{'relative_path':x,'sha256':y} for x,y in [('a','1'),('b','2'),('c','3')]]}
        b={'files':[{'relative_path':x,'sha256':y} for x,y in [('a','1'),('b','9'),('d','4')]]}
        self.assertEqual([r['status'] for r in compare(a,b)],['UNCHANGED','CHANGED','REMOVED','ADDED'])

class RelationshipContractTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'fixture.db'
        with sqlite3.connect(self.path) as c:
            c.executescript((ROOT/'db/schema.sql').read_text('utf-8'))
            c.execute("INSERT INTO source_file VALUES(1,'synthetic',?,0,'EXTRACTED',NULL)",('0'*64,))
            for sid,code in [('ce-01',1),('ce-05',5)]:
                c.execute("INSERT INTO scenario VALUES(?,?,?,184,2,'STANDARD','TEST',1,'PARSED_REVIEW',3,3,'TEST')",(sid,code,sid))
            for id,name in [(1,'동명'),(2,'동명'),(3,'다른무장')]:
                c.execute("INSERT INTO officer VALUES(?,?,'','HISTORICAL','TEST')",(id,name))
                for sid in ['ce-01','ce-05']:
                    c.execute("INSERT INTO officer_state(scenario_id,officer_id,name,state,raw_state,leadership,strength,intelligence,politics,charisma,record_offset,record_sha256,verification) VALUES(?,?,?,'FREE',8,50,50,50,50,50,0,?,'TEST')",(sid,id,name,'0'*64))
                    c.execute("INSERT INTO officer_personality(scenario_id,officer_id,verification) VALUES(?,?,'UNKNOWN')",(sid,id))
            c.execute("INSERT INTO relationship_scope VALUES(1,'ce-01','SCENARIO_COMPLETE_RECORDS','TEST')")
            c.execute("INSERT INTO relationship_scope VALUES(2,'ce-05','SCENARIO_COMPLETE_RECORDS','TEST')")
            c.execute("INSERT INTO relationship_edge VALUES(1,1,2,'AFFINITY',0,0)")
            c.execute("INSERT INTO relationship_edge VALUES(1,2,1,'AFFINITY',0,0)")
            c.execute("INSERT INTO relationship_edge VALUES(1,3,1,'DISLIKE',0,0)")
        c.close()
        self.q=Queries(self.path)
    def tearDown(self):self.temp.cleanup()
    def test_incoming_outgoing_and_duplicate_names(self):
        r=self.q.relationships(1,'ce-01')
        self.assertEqual([(x['type'],x['target_id']) for x in r['outgoing']],[('AFFINITY',2)])
        self.assertEqual({(x['type'],x['target_id']) for x in r['incoming']},{('AFFINITY',2),('DISLIKE',3)})
        self.assertEqual(self.q.relationships(3,'ce-01')['incoming'],[])
    def test_empty_scenario_does_not_fall_back(self):
        r=self.q.relationships(1,'ce-05');self.assertEqual(r['outgoing'],[]);self.assertEqual(r['incoming'],[])
    def test_unknown_is_null_not_zero(self):
        row=self.q.officer(1,'ce-01');self.assertTrue(all(x['value'] is None for x in row['personality']))
        with sqlite3.connect(self.path) as c:c.execute("UPDATE officer_personality SET integrity=0,verification='VERIFIED' WHERE scenario_id='ce-01' AND officer_id=1")
        c.close()
        self.assertEqual(self.q.officer(1,'ce-01')['personality'][0]['value'],0)
    def test_read_only_and_filters(self):
        with self.q.connect() as c:
            with self.assertRaises(sqlite3.OperationalError):c.execute('DELETE FROM officer')
        with self.assertRaises(ValidationError):self.q.officers({'sort':'name; DROP TABLE officer'})
        with self.assertRaises(ValidationError):self.q.officers({'page_size':'999'})
        self.assertEqual(self.q.officers({'scenario':'ce-01','q':'동명'})['total'],2)
        self.assertEqual(self.q.officers({'scenario':'ce-01','ids':''})['total'],0)

@unittest.skipUnless((ROOT/'db/ce-24966116-r3.final.db').exists(),'Real snapshot candidate not built')
class CandidateIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=ROOT/'db/ce-24966116-r3.final.db';cls.q=Queries(cls.db)
        cls.server=create_server('127.0.0.1',0,cls.db);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_address[1]}'
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def test_structure_and_release_block(self):
        result=validate(self.db);self.assertTrue(result['structural_pass']);self.assertFalse(result['release_ready'])
    def test_source_identity_and_policy(self):
        row=self.q.officer(521,'ce-05');self.assertEqual(row['name'],'조조');self.assertEqual(row['policy'],'문사무비');self.assertEqual(row['policy_level'],3)
        self.assertNotEqual(self.q.officer(522,'ce-05')['name'],'조조')
    def test_combined_filters_unique(self):
        rows=self.q.officers({'scenario':'ce-05','trait':'196','page_size':'200'})
        ids=[x['officer_id'] for x in rows['items']];self.assertEqual(len(ids),len(set(ids)));self.assertGreater(len(ids),0)
    def test_scenario_mode_and_pending_rejected(self):
        for sid in ['ce-32','ce-100','ce-71']:
            with self.assertRaises(ValidationError):self.q.officers({'scenario':sid})
    def test_api_errors_and_routes(self):
        for path in ['/api/v1/health','/api/v1/meta','/api/v1/coverage','/api/v1/policies','/api/v1/policies/47','/api/v1/tactics','/api/v1/compare?ids=147,521','/api/v1/officers/147?scenario=ce-05','/']:
            with urlopen(self.url+path) as response:self.assertEqual(response.status,200)
        with urlopen(self.url+'/state.mjs') as response:self.assertIn('text/javascript',response.headers['Content-Type'])
        for path,status in [('/api/v1/officers?bad=1',400),('/api/v1/officers?page=0',400),('/api/v1/officers/999999',404),('/../db/ce-24966116-r3.final.db',404),('/api/v1/officers?q=a&q=b',400)]:
            with self.assertRaises(HTTPError) as got:urlopen(self.url+path)
            self.assertEqual(got.exception.code,status);body=got.exception.read().decode();got.exception.close();self.assertNotIn('sqlite',body);self.assertNotIn(str(ROOT),body)

if __name__=='__main__':unittest.main()

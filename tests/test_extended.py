import sqlite3
import unittest
from pathlib import Path
from web.queries import Queries,ValidationError
from extractors.ce import interpret_record
from extractors.lwc import FormatError

ROOT=Path(__file__).resolve().parents[1]
class ExtendedCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.q=Queries(ROOT/'db/ce-24966116-r3.final.db')
    def test_personality_raw_encoding_and_known_samples(self):
        cao=self.q.officer(521,'ce-05');values={x['key']:x['value'] for x in cao['personality']}
        self.assertEqual(values,dict(integrity=2,diplomacy=3,han_attitude=3,ambition=5,aggression=4))
        for item in cao['personality']:
            self.assertEqual(item['verification_status'],'CROSS_CHECKED');self.assertEqual(item['value'],3+item['evidence']['raw_value']//10)
        guan=self.q.officer(147,'ce-05');self.assertEqual(next(x['value'] for x in guan['personality'] if x['key']=='integrity'),5)
    def test_marriage_and_sibling_groups_keep_identity(self):
        row=self.q.officer(147,'ce-05')
        self.assertEqual({x['target_id'] for x in row['relationships']['outgoing'] if x['type']=='SWORN_SIBLING'},{656,952})
        zhuge=self.q.officer(440,'ce-05');self.assertEqual([x['target_id'] for x in zhuge['relationships']['outgoing'] if x['type']=='MARRIAGE'],[249])
    def test_tactics_and_source_descriptions(self):
        cao=self.q.officer(521,'ce-05');self.assertIn('위무지강',[x['name'] for x in cao['tactics']]);self.assertTrue(cao['policy_detail']['description'])
        self.assertIn('명령설정',self.q.codex('trait',1)['items'][0]['description'])
        self.assertEqual([x['id'] for x in cao['policy_detail']['components']],[10,11,12,13,39,42])
        self.assertFalse(any(x['name']=='정책' for x in self.q.codex('policy')['items']))
    def test_multitrait_all_any_and_relation(self):
        both=self.q.officers({'trait':'14,59','trait_mode':'all','page_size':'200'})['items']
        any_=self.q.officers({'trait':'14,59','trait_mode':'any','page_size':'200'})['items']
        self.assertIn(521,[x['officer_id'] for x in both]);self.assertGreaterEqual(len(any_),len(both))
        related=self.q.officers({'relation_to':'147','relation_type':'SWORN_SIBLING','page_size':'200'})['items']
        self.assertEqual({x['officer_id'] for x in related},{656,952})
        for value in ['14,14','14,','1;DROP','0','1,2,3,4,5,6,7,8,9,10,11']:
            with self.assertRaises(ValidationError):self.q.officers({'trait':value})
    def test_compare_and_stored_order(self):
        self.assertEqual([x['officer_id'] for x in self.q.compare('952,147','ce-05')['items']],[952,147])
        self.assertEqual([x['officer_id'] for x in self.q.officers({'ids':'952,147,521','sort':'input'})['items']],[952,147,521])
        for ids in ['147','147,147','147,521,656,952']:
            with self.assertRaises(ValidationError):self.q.compare(ids)
    def test_non_discrete_personality_is_rejected(self):
        record=bytearray(316);record[276:278]=(7).to_bytes(2,'little')
        row={'record_offset':0,'source_id':1,'name':'fixture','courtesy_name':'','record_sha256':'0'*64}
        dictionary={k:[{'name':'invalid'}] for k in ['formation','settlement','doctrine','policy','trait','tactic']}
        with self.assertRaisesRegex(FormatError,'personality'):interpret_record(bytes(record),row,dictionary)

if __name__=='__main__':unittest.main()

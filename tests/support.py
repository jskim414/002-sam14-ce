"""Small invented API/DOM fixture. No game file or extracted database is read."""
from pathlib import Path
import os
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
REAL_DATABASE = Path(os.environ['CE_TEST_DATABASE']).resolve() if os.environ.get('CE_TEST_DATABASE') else None


def make_fixture(path):
    with sqlite3.connect(path) as c:
        c.executescript((ROOT/'db/schema.sql').read_text('utf-8'))
        c.execute('INSERT INTO release_profile VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                  ('synthetic-test','synthetic','ko','CE','0'*64,'0'*64,'0'*64,'0'*40,'2000-01-01T00:00:00Z',0,'["Synthetic fixture"]'))
        c.execute("INSERT INTO source_file VALUES(1,'SYNTHETIC-NO-GAME-DATA',?,0,'EXTRACTED','invented test data')",('0'*64,))
        for code in (5,32,33):
            sid=f'ce-{code:02}'
            c.execute("INSERT INTO scenario VALUES(?,?,?,190,1,'STANDARD','SYNTHETIC',1,'PARSED_REVIEW',3,3,'SYNTHETIC')",(sid,code,f'합성 시나리오 {code}'))
            c.execute("INSERT INTO relationship_scope VALUES(?,?,'SCENARIO_COMPLETE_RECORDS','SYNTHETIC')",(code,sid))
        for kind,id,name in [('trait',14,'합성 개성 A'),('trait',196,'합성 개성 B'),('policy',47,'합성 정책'),('policy',10,'합성 구성'),('policy_effect',10,'합성 효과'),('doctrine',1,'합성 주의'),('formation',1,'합성 진형'),('tactic',1,'위무지강'),('scenic',1,'합성 명승'),('strategy',1,'합성 방책'),('literature',1,'합성 시문'),('merit',1,'합성 공로')]:
            c.execute('INSERT INTO dictionary VALUES(?,?,?,1,0)',(kind,id,name))
            c.execute("INSERT INTO dictionary_detail VALUES(?,?,?,'SYNTHETIC')",(kind,id,'테스트용 설명'))
        c.execute('INSERT INTO policy_component VALUES(47,10,0)')
        for level in range(1,11):c.execute("INSERT INTO policy_level_effect VALUES(10,?,?,NULL,'RAW_SOURCE_UNIT_UNRESOLVED',1,0)",(level,level*2))
        # Familiar labels are test identifiers; all rows, statistics and edges
        # here are hand-authored and are never used to validate game semantics.
        for id,name in [(147,'관우'),(521,'조조'),(952,'유비')]:
            c.execute("INSERT INTO officer VALUES(?,?,'','HISTORICAL','SYNTHETIC')",(id,name))
            for code in (5,32,33):
                sid=f'ce-{code:02}'
                c.execute("INSERT INTO officer_state(scenario_id,officer_id,name,state,raw_state,force_id,force_name,leadership,strength,intelligence,politics,charisma,policy_id,policy,policy_level,doctrine_id,doctrine,record_offset,record_sha256,verification) VALUES(?,?,?,'ACTIVE_FORCE',4,1,'합성 세력',50,50,50,50,50,47,'합성 정책',3,1,'합성 주의',0,?,'SYNTHETIC')",(sid,id,name,'0'*64))
                c.execute("INSERT INTO officer_personality VALUES(?,?,2,3,3,5,4,'CROSS_CHECKED')",(sid,id))
                for key,value,offset in [('integrity',2,278),('diplomacy',3,290),('han_attitude',3,292),('ambition',5,294),('aggression',4,276)]:
                    c.execute("INSERT INTO personality_evidence VALUES(?,?,?,?,?,'I16_DELTA_10_BASE_3')",(sid,id,key,(value-3)*10,offset))
                c.execute('INSERT INTO officer_kinship VALUES(?,?,NULL,NULL)',(sid,id))
                for kind,value,slot in [('trait',14,0),('trait',196,1),('tactic',1,0),('formation',1,0)]:
                    c.execute('INSERT INTO officer_dictionary VALUES(?,?,?,?,?)',(sid,id,kind,value,slot))
        c.execute("INSERT INTO relationship_edge VALUES(5,147,521,'AFFINITY',0,0)")
        c.execute("INSERT INTO coverage VALUES('synthetic',3,3,'PASS','Invented fixture only')")
    c.close()
    return path

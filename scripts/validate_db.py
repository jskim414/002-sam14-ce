"""Validate candidate structure. --release fails until semantic gates are closed."""
import argparse
import json
from pathlib import Path
import sqlite3
from common import sha256,write_json

def validate(database: Path) -> dict:
    conn=sqlite3.connect(database.resolve(strict=True).as_uri()+'?mode=ro',uri=True)
    checks={}
    try:
        checks['integrity']=conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        checks['foreign_keys']=not conn.execute('PRAGMA foreign_key_check').fetchall()
        checks['expected_rows']=not conn.execute('SELECT s.id FROM scenario s LEFT JOIN officer_state o ON o.scenario_id=s.id WHERE s.status="PARSED_REVIEW" GROUP BY s.id HAVING count(o.officer_id)<>s.expected_rows').fetchall()
        checks['relationship_scope_membership']=not conn.execute('SELECT 1 FROM relationship_edge e JOIN relationship_scope r ON r.id=e.scope_id LEFT JOIN officer_state f ON f.scenario_id=r.scenario_id AND f.officer_id=e.from_officer_id LEFT JOIN officer_state t ON t.scenario_id=r.scenario_id AND t.officer_id=e.to_officer_id WHERE f.officer_id IS NULL OR t.officer_id IS NULL LIMIT 1').fetchall()
        checks['no_self_relationship']=not conn.execute('SELECT 1 FROM relationship_edge WHERE from_officer_id=to_officer_id').fetchall()
        checks['all_personality_rows']=conn.execute('SELECT count(*) FROM officer_state').fetchone()[0]==conn.execute('SELECT count(*) FROM officer_personality').fetchone()[0]
        checks['unverified_personality_not_fabricated']=not conn.execute("SELECT 1 FROM officer_personality WHERE verification='UNKNOWN' AND (integrity IS NOT NULL OR diplomacy IS NOT NULL OR han_attitude IS NOT NULL OR ambition IS NOT NULL OR aggression IS NOT NULL) LIMIT 1").fetchall()
        checks['all_files_classified']=not conn.execute("SELECT 1 FROM source_file WHERE processing_status='PENDING'").fetchall()
        checks['source_lineage']=not conn.execute('SELECT 1 FROM officer_state WHERE record_offset<0 OR length(record_sha256)<>64').fetchall()
        checks['policy_reference']=not conn.execute("SELECT 1 FROM officer_state s LEFT JOIN dictionary d ON d.kind='policy' AND d.id=s.policy_id WHERE s.policy_id IS NOT NULL AND d.id IS NULL LIMIT 1").fetchall()
        checks['doctrine_reference']=not conn.execute("SELECT 1 FROM officer_state s LEFT JOIN dictionary d ON d.kind='doctrine' AND d.id=s.doctrine_id WHERE s.doctrine_id IS NOT NULL AND d.id IS NULL LIMIT 1").fetchall()
        checks['policy_components']=not conn.execute("SELECT 1 FROM policy_component p LEFT JOIN dictionary a ON a.kind='policy' AND a.id=p.policy_id LEFT JOIN dictionary b ON b.kind='policy' AND b.id=p.component_id WHERE a.id IS NULL OR b.id IS NULL OR p.slot NOT BETWEEN 0 AND 7 LIMIT 1").fetchall()
        checks['all_kinship_rows']=conn.execute('SELECT count(*) FROM officer_state').fetchone()[0]==conn.execute('SELECT count(*) FROM officer_kinship').fetchone()[0]
        fields=['integrity','diplomacy','han_attitude','ambition','aggression']
        offsets=dict(integrity=278,diplomacy=290,han_attitude=292,ambition=294,aggression=276)
        checks['personality_evidence']=True
        for field in fields:
            if conn.execute(f"SELECT 1 FROM officer_personality p JOIN officer_state s USING(scenario_id,officer_id) LEFT JOIN personality_evidence e ON e.scenario_id=p.scenario_id AND e.officer_id=p.officer_id AND e.field=? WHERE p.verification='CROSS_CHECKED' AND (p.{field} IS NULL OR p.{field} NOT BETWEEN 1 AND 5 OR e.raw_value IS NULL OR e.raw_value NOT IN(-20,-10,0,10,20) OR p.{field}<>3+e.raw_value/10 OR e.record_offset<>s.record_offset+? OR e.encoding<>'I16_DELTA_10_BASE_3') LIMIT 1",(field,offsets[field])).fetchone():checks['personality_evidence']=False
        profile=conn.execute('SELECT release_ready,blockers_json FROM release_profile').fetchone()
        blockers=json.loads(profile[1])
        release_ready=bool(profile[0]) and not blockers and all(checks.values())
        return {'database_sha256':sha256(database),'structural_pass':all(checks.values()),'checks':checks,'release_ready':release_ready,'blockers':blockers}
    finally:conn.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--database',type=Path,required=True)
    p.add_argument('--report',type=Path);p.add_argument('--release',action='store_true');a=p.parse_args()
    report=validate(a.database)
    if a.report:write_json(a.report,report)
    print(json.dumps(report,ensure_ascii=True,indent=2))
    raise SystemExit(0 if report['structural_pass'] and (not a.release or report['release_ready']) else 2)

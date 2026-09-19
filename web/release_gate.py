"""One fail-closed semantic gate shared by API, validation and packaging."""
import json
import sqlite3

REQUIRED = ('officer_state', 'scenario_mode', 'officer_classification',
            'policy_effect_application', 'screen_validation', 'remote_operations',
            'source_comparison', 'integration_tests', 'reproducible_build', 'publication_approval')
ACCEPTED = {'PASS', 'SOURCE_MESSAGE_CROSS_CHECKED', 'SOURCE_GROUP_CROSS_CHECKED', 'STATIC_BASELINE_CROSS_CHECKED'}


def evaluate(conn):
    unresolved = []
    excluded = []
    try:
        profile = conn.execute('SELECT release_ready,blockers_json,inventory_sha256,profile_sha256,parser_sha256,git_sha FROM release_profile').fetchone()
        if profile is None:
            raise ValueError('Missing release profile')
        evidence = {row[0]: (row[1], json.loads(row[2])) for row in conn.execute('SELECT key,status,evidence_json FROM semantic_evidence')}
        lineage = dict(zip(('inventory_sha256','profile_sha256','parser_sha256','git_sha'), profile[2:]))
        for key in REQUIRED:
            status, detail = evidence.get(key, ('MISSING', {}))
            if status == 'EXCLUDED_BY_USER':
                excluded.append(key)
            if status not in ACCEPTED:
                unresolved.append({'key':key,'status':status})
            elif key not in ('officer_state','scenario_mode','officer_classification','policy_effect_application') and detail.get('lineage') != lineage:
                unresolved.append({'key':key,'status':'STALE_OR_MISSING_LINEAGE'})
        if conn.execute("SELECT 1 FROM scenario WHERE status<>'PARSED_REVIEW' LIMIT 1").fetchone():
            unresolved.append({'key':'scenario_bodies','status':'UNRESOLVED'})
        if not profile[0]:unresolved.append({'key':'promotion','status':'NOT_PROMOTED'})
        if json.loads(profile[1]):unresolved.append({'key':'profile_blockers','status':'UNRESOLVED'})
    except (sqlite3.Error, ValueError, TypeError, KeyError):
        unresolved.append({'key':'evidence_schema','status':'MISSING_OR_INVALID'})
    return {'release_ready':not unresolved, 'unresolved':unresolved, 'excluded':excluded}

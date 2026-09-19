"""Export the installed-file catalog without implying verified entitlement."""
import argparse
from pathlib import Path
import sqlite3
from common import write_json,sha256

def export(database):
    c=sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
    try:
        return {'database_sha256':sha256(database),'status':'LOCAL_REVIEW_ONLY',
                'ownership':'Installed depots are evidence of installation, not license verification',
                'content_packs':[dict(r) for r in c.execute('SELECT * FROM content_pack ORDER BY code')],
                'scenarios':[dict(r) for r in c.execute('SELECT s.*,f.relative_path,f.sha256 FROM scenario s JOIN source_file f ON f.id=s.source_file_id ORDER BY s.source_code')],
                'file_processing':[dict(r) for r in c.execute('SELECT processing_status,count(*) count FROM source_file GROUP BY processing_status')],
                'officer_categories':[dict(r) for r in c.execute('SELECT kind,kind_verification,count(*) count FROM officer GROUP BY kind,kind_verification')]}
    finally:c.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--database',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();write_json(a.output,export(a.database));print('Catalog written')

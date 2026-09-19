"""Compare two observed inventories without inventing a missing baseline."""
import argparse
import json
from pathlib import Path
from common import write_json

def compare(before: dict, after: dict) -> list[dict]:
    old = {x['relative_path']: x for x in before['files']}
    new = {x['relative_path']: x for x in after['files']}
    return [{'relative_path': key,
             'status': 'ADDED' if key not in old else 'REMOVED' if key not in new else
                       'UNCHANGED' if old[key]['sha256'] == new[key]['sha256'] else 'CHANGED',
             'before_sha256': old.get(key, {}).get('sha256'),
             'after_sha256': new.get(key, {}).get('sha256')}
            for key in sorted(old.keys() | new.keys())]

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--before', type=Path, required=True)
    p.add_argument('--after', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    write_json(a.output, {'files': compare(json.loads(a.before.read_text('utf-8')),
                                          json.loads(a.after.read_text('utf-8')))})

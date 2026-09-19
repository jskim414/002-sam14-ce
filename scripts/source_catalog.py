"""Load selected catalog records with hash-checked message provenance."""
import json
from pathlib import Path
import sys
import struct
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, sha256
from extractors.messages import decode_zp1, string_table, validate_enums
from extractors.ce import dictionaries


def catalog(shared, profile, inventory):
    spec = profile['message_source']
    path = ROOT / spec['snapshot_path']
    original = next(x for x in inventory['files'] if x['relative_path'] == spec['relative_path'])
    if sha256(path) != original['sha256'] or original['sha256'] != spec['sha256']:
        raise ValueError('Message snapshot hash mismatch')
    messages = string_table(decode_zp1(path.read_bytes()))
    validate_enums(messages)
    semantic=profile['semantic_source']
    executable=ROOT/semantic['snapshot_path']
    exe_record=next(x for x in inventory['files'] if x['relative_path']==semantic['relative_path'])
    if sha256(executable)!=exe_record['sha256'] or exe_record['sha256']!=semantic['sha256']:
        raise ValueError('Semantic evidence executable hash mismatch')
    executable_bytes=executable.read_bytes()
    for site in semantic['constant_evidence']:
        if 'constant_file_offset' in site and struct.unpack_from('<i',executable_bytes,site['constant_file_offset'])[0]!=site['constant']:
            raise ValueError('Policy default coefficient evidence mismatch')
    result = dictionaries(shared, profile)
    for kind, base in [('scenic', 5878), ('strategy', 6073)]:
        for row in result[kind]:
            message = messages[base + row['id']]
            row.update(description=message['text'], message_id=message['id'], message_offset=message['record_offset'])
    treasures=result.pop('treasure')
    result['literature'] = []
    for id in range(1, 21):
        title, desc = treasures[131+id], messages[6031 + id]
        if shared[title['record_offset']+14]!=26:raise ValueError('Literary item type changed')
        if id<=10 and title['name']!=messages[5163+id]['text']:raise ValueError('Literary item/title enum disagreement')
        result['literature'].append({'id':id, 'name':title['name'], 'record_offset':title['record_offset'],
                                    'description':desc['text'], 'message_id':desc['id'], 'message_offset':desc['record_offset'],
                                    'attributes':{'author':messages[5989 + id]['text'],
                                                                    'era':messages[6010 + id]['text'],
                                                                    'treasure_id':title['id'],
                                                                    'scope':'Literary works catalog; event trigger conditions not extracted'}})
    for row in result['tactic']:
        start = row['record_offset']
        category = shared[start + 48]
        effects = list(shared[start + 80:start + 82])
        if category > 8 or any(x > 23 for x in effects):
            raise ValueError('Unknown tactic category/effect reference')
        labels = [messages[337 + x]['text'] for x in effects if x]
        row['attributes'] = {'category':messages[327 + category]['text'],
                             'effects':[{'id':x, 'label':messages[337+x]['text']} for x in effects if x],
                             'scope':'Effect types only; magnitude, targeting and duration not interpreted'}
        if labels:
            row['description'] = messages[327 + category]['text'] + ' · ' + ' / '.join(labels)
            row['description_verification'] = 'SOURCE_ENUM_COMPOSITION'
    return result, messages

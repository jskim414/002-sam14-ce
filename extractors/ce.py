"""Measured CE build 24966116 layout. Semantic validation is incomplete.

All offsets are bounded and reported. No inferred personality values are emitted.
"""
from __future__ import annotations
import re
import struct
from .lwc import FormatError
from .messages import STATE_CODES

def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from('<H',data,offset)[0]

def fixed_text(data: bytes, offset: int, size: int) -> str:
    return data[offset:offset+size].decode('utf-16le').split('\0')[0]

def dictionaries(data: bytes, profile: dict) -> dict:
    result={}
    for kind, layout in profile['static_tables'].items():
        start,size,count=layout['offset'],layout['size'],layout['count']
        if start+size*count>len(data):raise FormatError(f'{kind}: table exceeds file')
        if struct.unpack_from('<II',data,start-8)!=(layout['section'],count):
            raise FormatError(f'{kind}: unexpected section/count')
        rows=[]
        for i in range(count):
            name=fixed_text(data,start+i*size,layout['name_bytes'])
            row={'id':i,'name':name,'record_offset':start+i*size}
            if 'description_offset' in layout:
                row['description']=fixed_text(data,start+i*size+layout['description_offset'],layout['description_bytes'])
            if kind=='policy':row['components']=[x for x in data[start+i*size+136:start+i*size+144] if x]
            if kind=='policy_effect':
                row['level_values']=list(struct.unpack_from('<10h',data,start+i*size+114))
                row['unit']=profile['policy_effect_units'].get(str(i))
                row['attributes']={'unlocks':[{'level':int(level),'name':name} for level,name in re.findall(r'(\d+):([^，,)]+)',row.get('description',''))],
                                   'numeric_applicability':'NOT_APPLICABLE' if i in (13,14,24) else 'STATIC_BASELINE' if row['unit'] else 'UNUSED_SLOT',
                                   'direction':'DECREASE' if i in (11,22,38) else 'INCREASE',
                                   'condition':'기본 계수 기준. 설정 변경·추가 보정·상한·반올림 전의 정책 효과표이며 현재 세력 효과 계산이 아님'}
            if kind=='strategy':
                row['attributes']={'adjacent_ids':[x for x in data[start+i*size+31:start+(i+1)*size] if x],
                                   'scope':'Static name, description and adjacent panel references'}
            if kind=='merit':
                threshold=struct.unpack_from('<h',data,start+i*size+28)[0]
                row['description']=f'공로 기준 {threshold:,}. 승급·강등의 추가 조건과 보정은 이 표에 포함하지 않습니다.'
                row['description_verification']='SOURCE_THRESHOLD_COMPOSITION'
                row['attributes']={'credit_threshold':threshold,'scope':'Rank names and signed credit thresholds only'}
            rows.append(row)
        result[kind]=rows
    # Global settlement references continue after the city/tribal-city slots.
    for gate in result['gate'][1:]:
        result['settlement'].append({**gate,'id':len(result['settlement'])})
    return result


def classify_record(row: dict, profile: dict, messages: list[dict]) -> str:
    """Source slot groups, never a statement of historical truth or ownership."""
    for group in profile['officer_groups']:
        first,last=group['source_ids']
        if first<=row['source_id']<=last:
            expected=group['record_start']+row['source_id']-first
            if row['record_index']!=expected:raise FormatError('Officer source group/index mismatch')
            if group.get('biography_offset') is not None:
                text=messages[group['biography_offset']+expected]['text']
                missing=not text or text=='무효'
                documented=row['source_id'] in group.get('biography_missing_ids',[])
                if missing!=documented:raise FormatError('Officer biography presence differs from measured profile')
            return group['kind']
    raise FormatError(f'Unclassified officer source ID {row["source_id"]}')

def scenario_header(raw: bytes, filename: str) -> dict:
    if raw[4:20]!=b'SN14SCEXVER0001\0' or len(raw)<754:
        raise FormatError('Unsupported CE scenario outer header')
    code=int(re.fullmatch(r'scedaexce(\d+)\.s14',filename).group(1))
    if u16(raw,462)!=code:raise FormatError('Filename/header scenario ID mismatch')
    mode_code=raw[458]
    mode={1:'STANDARD',2:'TUTORIAL',4:'WAR_CHRONICLES'}.get(mode_code,'UNCLASSIFIED')
    month=raw[461]
    if not 1<=month<=12:raise FormatError('Scenario month outside calendar')
    return {'id':f'ce-{code:02}', 'source_code':code, 'name':fixed_text(raw,422,34),
            'start_year':u16(raw,456),'start_month':month,'mode':mode,
            'mode_verification':'SOURCE_MESSAGE_CROSS_CHECKED'}

def interpret_record(data: bytes, row: dict, dictionary: dict) -> dict:
    start=row['record_offset'];record=data[start:start+316]
    if len(record)!=316:raise FormatError('Truncated officer')
    def label(kind, code):
        if not 0<=code<len(dictionary[kind]):raise FormatError(f'Invalid {kind} reference {code}')
        return dictionary[kind][code]['name'] if code else None
    traits=[u16(record,p) for p in range(176,194,2)]
    tactics=[x for x in record[198:208] if x]
    formations=[i for i in range(1,len(dictionary['formation'])) if int.from_bytes(record[194:198],'little') & (1<<i)]
    raw_state=record[161]
    if raw_state not in STATE_CODES:raise FormatError(f'Unknown officer state {raw_state}')
    state=STATE_CODES[raw_state]
    out={'id':row['source_id'],'name':row['name'],'courtesy_name':row['courtesy_name'],
         'state':state,'raw_state':raw_state,'force_id':record[156] or None,
         'settlement_id':u16(record,157) or None,'settlement_name':label('settlement',u16(record,157)),
         'appearance_year':u16(record,217) or None,'birth_year':u16(record,219) or None,
         'death_year':u16(record,221) or None,
         'leadership':record[166],'strength':record[167],'intelligence':record[168],
         'politics':record[169],'charisma':record[170],'affinity':record[231],
         'doctrine_id':record[274] or None,'doctrine':label('doctrine',record[274]),
         'policy_id':record[208] or None,'policy':label('policy',record[208]),
         'policy_level':record[300] if record[208] else None,
         'record_offset':start,'record_sha256':row['record_sha256'],
         'traits':[x for x in traits if x], 'formations':formations,'tactics':tactics,
         'spouse_id':u16(record,152) or None,'sworn_group_id':u16(record,154) or None,
         'personality':{},
         'relationships':{'AFFINITY':[u16(record,p) for p in range(232,248,2) if u16(record,p)],
                          'DISLIKE':[u16(record,p) for p in range(248,264,2) if u16(record,p)]}}
    for id in out['traits']:label('trait',id)
    if 'tactic' in dictionary:
        for id in tactics:label('tactic',id)
    # Signed 16-bit deltas, independently reported by an original format
    # researcher (2021-03-25 post 699), then range-checked on the CE snapshot.
    # These are cross-checked values; game-screen verification remains separate.
    for key,p in [('aggression',276),('integrity',278),('diplomacy',290),('han_attitude',292),('ambition',294)]:
        raw=struct.unpack_from('<h',record,p)[0]
        if raw not in (-20,-10,0,10,20):raise FormatError(f'Unsupported personality encoding: {key}={raw}')
        out['personality'][key]={'raw':raw,'value':3+raw//10,'offset':start+p}
    if out['spouse_id']:out['relationships']['MARRIAGE']=[out['spouse_id']]
    return out

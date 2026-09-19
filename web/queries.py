from __future__ import annotations
import json
from contextlib import contextmanager
from pathlib import Path
import sqlite3

class ValidationError(ValueError): pass
class NotFound(LookupError): pass

STATE_LABELS={'ACTIVE_FORCE':'현역','FREE':'재야','UNAPPEARED':'미등장','DEAD_OR_RETIRED':'사망·은퇴',
              'DISABLED':'미배치','UNVERIFIED_STATUS':'신분 확인 중'}
STAT_KEYS=('leadership','strength','intelligence','politics','charisma')

def positive(value,default,minimum=1,maximum=200):
    if value is None or value=='':return default
    try: result=int(value)
    except (ValueError,TypeError):raise ValidationError('숫자 형식이 올바르지 않습니다.')
    if not minimum<=result<=maximum:raise ValidationError('숫자가 허용 범위를 벗어났습니다.')
    return result

class Queries:
    def __init__(self,database: Path):
        self.database=database.resolve(strict=True)
        if not self.database.is_file():raise ValueError('Database is not a file')

    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.database.as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
        try:
            c.execute('PRAGMA query_only=ON');c.execute('PRAGMA foreign_keys=ON');yield c
        finally:c.close()

    def health(self):
        with self.connect() as c:
            p=c.execute('SELECT id,build_id,release_ready,parser_sha256 FROM release_profile').fetchone()
            return {'status':'ok','database':'read-only','schema_version':c.execute('SELECT max(version) FROM schema_version').fetchone()[0],
                    'release_id':p['id'],'build_id':p['build_id'],'parser_sha256':p['parser_sha256'],'release_ready':bool(p['release_ready'])}

    def coverage(self):
        with self.connect() as c:
            p=dict(c.execute('SELECT * FROM release_profile').fetchone())
            return {'release_id':p['id'],'build_id':p['build_id'],'data_as_of':p['captured_at'],
                    'release_ready':bool(p['release_ready']),'status':'PARTIAL',
                    'blockers':json.loads(p['blockers_json']),
                    'datasets':[dict(r) for r in c.execute('SELECT * FROM coverage ORDER BY key')]}

    def scenarios(self):
        with self.connect() as c:
            return [dict(r) for r in c.execute('SELECT id,source_code,name,start_year,start_month,mode,status,delivery_status,expected_rows FROM scenario ORDER BY source_code')]

    def meta(self):
        with self.connect() as c:
            result={**self.health(),'default_scenario':'ce-05','states':STATE_LABELS,
                    'capabilities':{'officers':True,'relationships':True,'personality_verified':False,'publication':False}}
            for kind in ('doctrine','policy','trait','formation','tactic'):
                if kind in ('doctrine','policy'):
                    used=f'SELECT DISTINCT {kind}_id FROM officer_state'
                else:used="SELECT DISTINCT dictionary_id FROM officer_dictionary WHERE kind='"+kind+"'"
                result['policies' if kind=='policy' else kind+'s']=[dict(r) for r in c.execute(f'SELECT d.id,d.name,x.description FROM dictionary d LEFT JOIN dictionary_detail x ON x.kind=d.kind AND x.dictionary_id=d.id WHERE d.kind=? AND d.id IN ({used}) AND d.id<>0 ORDER BY d.name',(kind,))]
            return result

    def codex(self,kind,id=None):
        if kind not in ('trait','policy','formation','tactic','doctrine'):raise ValidationError('도감 종류가 올바르지 않습니다.')
        with self.connect() as c:
            args=[kind];where='d.kind=? AND d.id<>0'
            if id is not None:where+=' AND d.id=?';args.append(id)
            placeholders={'trait':'개성','policy':'정책','formation':'진형','tactic':'전법','doctrine':'주의'}
            rows=[dict(r) for r in c.execute('SELECT d.id,d.name,x.description,x.verification FROM dictionary d LEFT JOIN dictionary_detail x ON x.kind=d.kind AND x.dictionary_id=d.id WHERE '+where+' ORDER BY d.id',args) if r['name'] and r['name'] not in (placeholders[kind],'무효')]
            if id is not None and not rows:raise NotFound('도감 항목을 찾을 수 없습니다.')
            if kind=='policy':
                for row in rows:
                    row['components']=[dict(x) for x in c.execute("SELECT d.id,d.name,t.description FROM policy_component p JOIN dictionary d ON d.kind='policy' AND d.id=p.component_id LEFT JOIN dictionary_detail t ON t.kind=d.kind AND t.dictionary_id=d.id WHERE p.policy_id=? AND p.component_id<>p.policy_id ORDER BY p.slot",(row['id'],))]
            return {'kind':kind,'items':rows,'coverage_status':'SOURCE_TEXT_PARTIAL_EFFECT_FORMULAS'}

    def compare(self,ids,scenario=None):
        values=self.ids(ids,3)
        if len(values)<2:raise ValidationError('비교할 무장 2~3명을 선택해주세요.')
        return {'items':[self.officer(id,scenario) for id in values],'scenario_id':scenario or 'ce-05'}

    @staticmethod
    def ids(value,limit=10):
        parts=value.split(',') if value else []
        if not parts or len(parts)>limit or any(not x.isdecimal() for x in parts):raise ValidationError('ID 목록이 올바르지 않습니다.')
        ids=[positive(x,None,maximum=100000) for x in parts]
        if len(ids)!=len(set(ids)):raise ValidationError('ID가 중복되었습니다.')
        return ids

    @staticmethod
    def context(c,sid):
        row=c.execute('SELECT id,captured_at FROM release_profile').fetchone()
        return {'release_id':row['id'] if row else None,'data_as_of':row['captured_at'] if row else None,
                'scenario_id':sid,'coverage_status':'PARTIAL'}

    @staticmethod
    def scenario(c, value):
        row=c.execute('SELECT * FROM scenario WHERE id=?',(value or 'ce-05',)).fetchone()
        if not row:raise NotFound('시나리오를 찾을 수 없습니다.')
        if row['status']!='PARSED_REVIEW' or row['mode']!='STANDARD':
            raise ValidationError('이 시나리오는 일반 무장 탐색을 아직 지원하지 않습니다.')
        return row['id']

    def officers(self,filters):
        allowed={'scenario','q','state','force','doctrine','policy','level_min','trait','trait_mode','formation','tactic','kind','sort','order','page','page_size','ids','relation_to','relation_type','relation_direction'}
        if set(filters)-allowed:raise ValidationError('지원하지 않는 검색 조건입니다.')
        page=positive(filters.get('page'),1,maximum=100000);limit=positive(filters.get('page_size'),30)
        sort=filters.get('sort','name');order=filters.get('order','asc').lower()
        if sort not in ('name','policy_level','appearance_year','input',*STAT_KEYS) or order not in ('asc','desc'):raise ValidationError('정렬 조건이 올바르지 않습니다.')
        trait_mode=filters.get('trait_mode','all')
        if trait_mode not in ('all','any'):raise ValidationError('개성 조합 조건이 올바르지 않습니다.')
        kind=filters.get('kind','HISTORICAL')
        if kind not in ('HISTORICAL','BONUS','ALL'):raise ValidationError('무장 분류가 올바르지 않습니다.')
        q=filters.get('q','').strip()
        if len(q)>80:raise ValidationError('검색어는 80자 이내로 입력해주세요.')
        with self.connect() as c:
            sid=self.scenario(c,filters.get('scenario'));clauses=['s.scenario_id=?'];args=[sid]
            if kind!='ALL':clauses.append('o.kind=?');args.append(kind)
            else:clauses.append("o.kind NOT IN ('NPC','PLACEHOLDER')")
            if q:
                clauses.append("(s.name LIKE ? ESCAPE '\\' OR o.courtesy_name LIKE ? ESCAPE '\\')")
                value='%'+q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%';args.extend([value,value])
            state=filters.get('state')
            if state:
                if state not in STATE_LABELS:raise ValidationError('상태가 올바르지 않습니다.')
                clauses.append('s.state=?');args.append(state)
            for key,column in [('force','force_id'),('doctrine','doctrine_id'),('policy','policy_id')]:
                if filters.get(key):clauses.append('s.'+column+'=?');args.append(positive(filters[key],None,maximum=10000))
            if filters.get('level_min'):
                clauses.append('s.policy_level>=?');args.append(positive(filters['level_min'],None,minimum=0,maximum=255))
            for key in ('trait','formation','tactic'):
                if filters.get(key):
                    values=self.ids(filters[key])
                    sub=[]
                    for value in values:
                        sub.append('EXISTS(SELECT 1 FROM officer_dictionary x WHERE x.scenario_id=s.scenario_id AND x.officer_id=s.officer_id AND x.kind=? AND x.dictionary_id=?)')
                        args.extend([key,value])
                    clauses.append('('+(' OR ' if key=='trait' and trait_mode=='any' else ' AND ').join(sub)+')')
            if filters.get('relation_to'):
                target=positive(filters['relation_to'],None,maximum=100000)
                direction=filters.get('relation_direction','outgoing');reltype=filters.get('relation_type','AFFINITY')
                if direction not in ('outgoing','incoming') or reltype not in ('AFFINITY','DISLIKE','MARRIAGE','SWORN_SIBLING'):raise ValidationError('관계 조건이 올바르지 않습니다.')
                src,dst=('from_officer_id','to_officer_id') if direction=='outgoing' else ('to_officer_id','from_officer_id')
                clauses.append(f'EXISTS(SELECT 1 FROM relationship_edge e JOIN relationship_scope r ON r.id=e.scope_id WHERE r.scenario_id=s.scenario_id AND e.{src}=s.officer_id AND e.{dst}=? AND e.type=?)');args.extend([target,reltype])
            elif filters.get('relation_direction') or filters.get('relation_type'):raise ValidationError('관계 대상 무장을 지정해주세요.')
            ids=[]
            if 'ids' in filters:
                raw=filters['ids'].split(',') if filters['ids'] else []
                if len(raw)>100:raise ValidationError('보관함 조회는 100명까지 지원합니다.')
                ids=self.ids(filters['ids'],100) if raw else []
                clauses.append('s.officer_id IN ('+','.join('?' for _ in ids)+')' if ids else '0')
                args.extend(ids)
            where=' AND '.join(clauses);base=' FROM officer_state s JOIN officer o ON o.id=s.officer_id WHERE '+where
            total=c.execute('SELECT count(*)'+base,args).fetchone()[0]
            ordering=f's.{sort} {order},s.officer_id'
            if sort=='input':
                if not ids:raise ValidationError('보관 순서 정렬에는 ID 목록이 필요합니다.')
                ordering='CASE s.officer_id '+' '.join(f'WHEN {id} THEN {i}' for i,id in enumerate(ids))+' END'
            rows=[dict(r) for r in c.execute('SELECT s.*,o.courtesy_name,o.kind'+base+' ORDER BY '+ordering+' LIMIT ? OFFSET ?',args+[limit,(page-1)*limit])]
            for row in rows:
                row['state_label']=STATE_LABELS[row['state']]
                row['traits']=self.attached(c,sid,row['officer_id'],'trait')
            return {'items':rows,'total':total,'page':page,'page_size':limit,**self.context(c,sid)}

    @staticmethod
    def attached(c,sid,id,kind):
        return [dict(r) for r in c.execute('SELECT d.id,d.name,dt.description FROM officer_dictionary x JOIN dictionary d ON d.kind=x.kind AND d.id=x.dictionary_id LEFT JOIN dictionary_detail dt ON dt.kind=d.kind AND dt.dictionary_id=d.id WHERE x.scenario_id=? AND x.officer_id=? AND x.kind=? ORDER BY x.slot',(sid,id,kind))]

    def relationships(self,id,scenario=None):
        with self.connect() as c:
            sid=self.scenario(c,scenario)
            if not c.execute('SELECT 1 FROM officer_state WHERE scenario_id=? AND officer_id=?',(sid,id)).fetchone():raise NotFound('무장을 찾을 수 없습니다.')
            scope=c.execute('SELECT * FROM relationship_scope WHERE scenario_id=?',(sid,)).fetchone()
            result={'outgoing':[],'incoming':[],'verification':scope['verification'],**self.context(c,sid),
                    'unverified_types':[],'screen_verified':False}
            for direction,src,dst in [('outgoing','from_officer_id','to_officer_id'),('incoming','to_officer_id','from_officer_id')]:
                result[direction]=[dict(r) for r in c.execute(f'SELECT r.type,o.id target_id,o.name target_name,o.courtesy_name FROM relationship_edge r JOIN officer o ON o.id=r.{dst} WHERE r.scope_id=? AND r.{src}=? ORDER BY r.type,o.name,o.id',(scope['id'],id))]
            return result

    def officer(self,id,scenario=None):
        with self.connect() as c:
            sid=self.scenario(c,scenario)
            row=c.execute('SELECT s.*,o.courtesy_name,o.kind FROM officer_state s JOIN officer o ON o.id=s.officer_id WHERE s.scenario_id=? AND s.officer_id=?',(sid,id)).fetchone()
            if not row:raise NotFound('무장을 찾을 수 없습니다.')
            result=dict(row);result['state_label']=STATE_LABELS[result['state']]
            for kind in ('trait','formation','tactic'):result[kind+'s']=self.attached(c,sid,id,kind)
            personality=c.execute('SELECT * FROM officer_personality WHERE scenario_id=? AND officer_id=?',(sid,id)).fetchone()
            result['personality']=[{'key':key,'label':label,'value':personality[key],'verification_status':personality['verification']}
                                   for key,label in [('integrity','의리'),('diplomacy','외교'),('han_attitude','한조'),('ambition','야망'),('aggression','호전')]]
            result['relationships']=self.relationships(id,sid)
            if personality['verification']=='CROSS_CHECKED':
                raw={r['field']:dict(r) for r in c.execute('SELECT field,raw_value,record_offset,encoding FROM personality_evidence WHERE scenario_id=? AND officer_id=?',(sid,id))}
                for item in result['personality']:item['evidence']=raw[item['key']]
            result['policy_detail']=self.codex('policy',result['policy_id'])['items'][0] if result['policy_id'] else None
            result['evidence']=dict(c.execute('SELECT f.relative_path,f.sha256 FROM source_file f JOIN scenario s ON s.source_file_id=f.id WHERE s.id=?',(sid,)).fetchone())
            result.update(self.context(c,sid))
            return result

    def forces(self,scenario=None):
        with self.connect() as c:
            sid=self.scenario(c,scenario)
            return [dict(r) for r in c.execute('SELECT DISTINCT force_id id,force_name name FROM officer_state WHERE scenario_id=? AND force_id IS NOT NULL AND force_name IS NOT NULL ORDER BY force_name',(sid,))]

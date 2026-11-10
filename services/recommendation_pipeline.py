"""One authoritative candidate/score/reason/render order; only source JSON supplies facts."""
from copy import deepcopy
import re
from services.activity_ranking import ACTIVITY_TRAITS, SIMILAR, MATCH_LABELS
from services.alternative_paths import RELATIONS, NEIGHBOURS, district, local_rows
from services.recommendations import recommend, eligibility, _budget
from services.personalization import profile_conditions, personal_note
from services.activities import availability_status


def explicit_activity(text):
    aliases={'걷기':('걷기','걷는','걷고','산책'), '슬로우조깅':('슬로우조깅',),
             '파크골프':('파크골프',),'체조':('체조',),'아쿠아로빅':('아쿠아로빅','수중운동'),
             '수영':('수영',),'숲체험':('숲체험','숲산책'),'미술':('그림','미술'),
             '가드닝':('가드닝','식물가꾸기'),'인문학':('인문학',),'국악공연':('국악',)}
    compact=re.sub(r'\s+','',text)
    if '말고' in compact:compact=compact.rsplit('말고',1)[1]
    matches=[(len(alias),kind) for kind,words in aliases.items() for alias in words if alias in compact]
    if not matches:return None
    longest=max(length for length,_ in matches)
    kinds={kind for length,kind in matches if length==longest}
    # Two different explicit activities require context, never an arbitrary first choice.
    all_kinds={kind for _,kind in matches}
    if len(all_kinds)>1 and not (all_kinds<={'걷기','숲체험'} or all_kinds<={'수영','아쿠아로빅'}):return None
    return next(iter(kinds)) if len(kinds)==1 else None


def anchor_request(text, request):
    request=deepcopy(request)
    compact=re.sub(r'\s+','',text)
    markers={
        'residence':('거주','살고','살아','사는','주민','구민'),
        'gender':('남성','남자','여성','여자','할머니','할아버지','엄마','어머니','아빠','아버지'),
        'beginner':('초보','처음','입문','배우','배워','경험','숙련'),
        'effort_preference':('가볍','가벼','무리하지','천천히','활발','보통','강하게'),
        'budget_amount':('원','무료','공짜','예산','돈','저렴'),
        'budget_unit':('회','번','달','월','일','금액'),
    }
    for field,words in markers.items():
        if field in request['update_fields'] and not any(word in compact for word in words):
            request['update_fields'].remove(field);request['conditions'][field]=None
    purpose_words={'운동':('운동','체육','걷','수영','조깅','체조','골프'),
                   '배우기':('배우','배워','초보','처음','입문'),
                   '관람':('관람','구경','보고','공연','전시'),
                   '교류':('친구','함께','같이','교류','사람'),
                   '휴식':('쉬','휴식','힐링')}
    if 'purpose' in request['update_fields'] and not any(word in compact for word in purpose_words.get(request['conditions'].get('purpose'),())):
        request['update_fields'].remove('purpose');request['conditions']['purpose']=None
    time_explicit=bool(re.search(r'오전|아침|오후|저녁|밤|낮|점심|새벽|일찍|퇴근|\d{1,2}시',compact))
    if 'time_slot' in request['update_fields'] and not time_explicit:
        request['update_fields'].remove('time_slot');request['conditions']['time_slot']=None
    if 'time_slot' in request['clear_fields'] and not ('시간' in compact or '상관없' in compact or '아무때' in compact):
        request['clear_fields'].remove('time_slot')
    districts=set(NEIGHBOURS)|{value for values in NEIGHBOURS.values() for value in values}
    stated=[value for value in districts if value in compact]
    if len(stated)==1:
        region=('부산 '+stated[0]) if '부산' in compact else stated[0]
        request['conditions']['region']=region
        if 'region' not in request['update_fields']:request['update_fields'].append('region')
        if 'region' in request['clear_fields']:request['clear_fields'].remove('region')
    kind=explicit_activity(text)
    if not kind:return request
    old_kind=request['conditions'].get('activity_type')
    expected='체육' if kind in ACTIVITY_TRAITS else '문화·취미' if kind in {'미술','가드닝','국악공연'} else None
    if expected and request['conditions'].get('category') not in {None,expected}:
        request['conditions']['category']=None
        if 'category' in request['update_fields']:request['update_fields'].remove('category')
    tags=request['conditions'].get('tags')
    if tags is not None:
        redundant={kind,old_kind}|({'산책','보행','걷기'} if kind=='걷기' else set())
        explicit=[tag for tag in tags if tag not in redundant and tag.replace(' ','') in re.sub(r'\s+','',text)]
        request['conditions']['tags']=explicit or None
        if not explicit and 'tags' in request['update_fields']:request['update_fields'].remove('tags')
    request['conditions']['activity_type']=kind
    if 'activity_type' not in request['update_fields']:request['update_fields'].append('activity_type')
    if 'activity_type' in request['clear_fields']:request['clear_fields'].remove('activity_type')
    return request


def score_program(row, conditions, *, as_of=None):
    requested=conditions.get('activity_type');kind=row['activity_type']
    tier=0 if kind==requested else 1 if kind in SIMILAR.get(requested,set()) else 2
    source=ACTIVITY_TRAITS.get(requested,{})
    target=ACTIVITY_TRAITS.get(kind,{})
    eligible,notes=eligibility(row,conditions)
    status=availability_status(row,as_of=as_of)
    parts={'activity':300-100*tier,
           'purpose':10 if conditions.get('purpose')=='운동' and row['category']=='체육' else 0,
           'movement':10 if source.get('movement') and source.get('movement')==target.get('movement') else 0,
           'effort':0,
           'region':10 if district(row['region'])==district(conditions.get('region')) else 0,
           'target':5 if eligible and not notes else 2 if eligible else -1000,
           'access':0,
           'time_preference':6 if conditions.get('_modes',{}).get('time_slot')=='preferred' and conditions.get('time_slot') in row['schedule']['time_slots'] else 0,
           'budget_preference':4 if conditions.get('_modes',{}).get('budget_amount')=='preferred' and _budget(row,conditions)=='match' else 0,
           'registration':{'open':3,'walk_in':2,'upcoming':1,'unknown':1,'closed':0,'ended':0}[status]}
    if not requested:
        reason='말씀하신 지역과 조건에서 확인한 공식 활동이에요.'
    elif kind==requested:
        reason='말씀하신 활동과 직접 일치하는 공식 프로그램이에요.'
    elif requested=='걷기' and kind=='슬로우조깅':
        reason='걷기처럼 보행 중심인 유사 운동이지만 속도와 실제 강도는 확인해야 해요.'
    elif tier==1:
        reason='말씀하신 활동과 움직임이나 목적이 이어지는 유사 활동으로 실제 강도는 확인해야 해요.'
    else:
        reason='움직이는 목적을 이어갈 수 있는 다른 활동으로 도구와 참여 조건을 확인해야 해요.' if row['category']=='체육' else '관심을 다른 방식으로 이어갈 수 있는 활동으로 주제와 참여 조건을 확인해 주세요.'
    note=personal_note(row,conditions,_budget(row,conditions))
    if note:reason+=' '+note
    return {'score':sum(parts.values()),'score_parts':parts,'match_tier':tier,
            'match_label':MATCH_LABELS[tier],'reason':reason}


def ordered_options(options, activities, conditions, *, as_of=None):
    official={row['id']:row for row in activities if not row['is_demo']}
    grouped={}
    for option in options:
        for candidate in option.get('rows',[]):
            row=official.get(candidate.get('id'))
            if not row or row['activity_type']!=option.get('activity_type'):continue
            kind=row['activity_type']
            rows=grouped.setdefault(kind,{})
            rows[row['id']]=deepcopy(row)
    result=[]
    for kind,rows in grouped.items():
        # Reapply all hard conditions so cached candidates never bypass qualification.
        changed=dict(conditions,activity_type=kind,region=district(conditions.get('region')) or conditions.get('region'))
        changed.pop('category',None);changed.pop('tags',None)
        outcome=recommend(list(rows.values()),changed,as_of=as_of)
        accepted=outcome['results'] or outcome['references']
        if not accepted:continue
        accepted.sort(key=lambda row:(-score_program(row,conditions,as_of=as_of)['score'],row['id']))
        assessment=score_program(accepted[0],conditions,as_of=as_of)
        result.append(dict(assessment,activity_type=kind,rows=accepted[:3],available=bool(outcome['results'])))
    return sorted(result,key=lambda option:(-option['score'],option['activity_type']))[:3]


def programme_options(activities, conditions, *, as_of=None):
    kinds=[kind for kind,_ in RELATIONS.get(conditions.get('activity_type'),[])]
    rows=local_rows(activities,conditions.get('region'))
    candidates=[{'activity_type':kind,'rows':[row for row in rows if row['activity_type']==kind]} for kind in kinds]
    return ordered_options(candidates,activities,conditions,as_of=as_of)


def prepare_view(state, activities, *, user_text="", as_of=None):
    """Final boundary re-sorts even persisted/reversed legacy session candidates."""
    state=deepcopy(state)
    query=profile_conditions(state)
    if state.get('flow')=='adjacent' or state.get('search_scope',{}).get('kind')=='adjacent' or (state.get('code')=='expansion_empty' and 'search_scope' not in state):
        # Migrate persisted pre-isolation states: old local cards are not new neighbours.
        if state.get('flow')!='adjacent' and not state.get('previous_local'):
            state['previous_local']={'region':state['conditions'].get('region'),'conditions':deepcopy(state['conditions']),
                'results':state.get('results',[]),'references':state.get('references',[]),'alternatives':state.get('alternatives',[])}
        approved=state.get('expansion_consent')==state['conditions'].get('region') and bool(state['conditions'].get('region'))
        outcome=adjacent_programmes(activities,query,consent=approved,as_of=as_of)
        state.update(flow='adjacent',alternatives=[],ideas=[],facilities=[],results=outcome['results'],references=outcome['references'],adjacent_groups=outcome['groups'])
        state['search_scope']={'kind':'adjacent','origin':state['conditions'].get('region'),'allowed':outcome['districts'],'covered':outcome['covered']}
        if not outcome['results'] and not outcome['references']:
            state.update(message=('현재'+' 확인된 인접 지역 프로그램 자료가 없습니다.' if not outcome['covered'] else '저장된 인접 지역 자료에서 조건에 맞는 프로그램을 확인하지 못했어요.')+' 실시간 웹 검색은 하지 않았어요.',code='expansion_empty')
        return state
    kind=explicit_activity(user_text)
    if (kind and state.get('flow')=='program' and state.get('code') not in {'apply','choose','question','start','demo'}
            and state['conditions'].get('activity_type')!=kind):
        state['conditions']['activity_type']=kind
        state['conditions'].pop('category',None);state['conditions'].pop('tags',None)
        query=profile_conditions(state)
        exact=recommend(local_rows(activities,state['conditions'].get('region')),query,as_of=as_of)
        state.update(results=exact['results'],references=exact['references'],code=exact['code'],selected_id=None,
                     alternatives=programme_options(activities,query,as_of=as_of),
                     message=kind+'에 맞는 공식 자료를 기준으로 다시 정리했어요.')
    if state.get('flow')=='program' and state.get('code') not in {'start','demo','ideas','question','choose'}:
        official={row['id']:row for row in activities if not row['is_demo']}
        for field in ('results','references'):
            unique={row['id']:row for row in state.get(field,[]) if row.get('id') in official}
            ranked=[]
            for row in unique.values():
                row=deepcopy(row)
                row.update(score_program(official[row['id']],query,as_of=as_of))
                ranked.append(row)
            state[field]=sorted(ranked,key=lambda row:(-row['score'],row['id']))[:3]
    if state.get('alternatives'):
        state['alternatives']=ordered_options(state['alternatives'],activities,query,as_of=as_of)
    # Do not show an independently ordered generic list alongside official alternatives.
    if state.get('alternatives'):state['ideas']=[]
    state['recommendation_trace']={'activity_type':state['conditions'].get('activity_type'),
        'mode':state.get('mode'),'ordered_activities':[o['activity_type'] for o in state.get('alternatives',[])],
        'scores':[o['score'] for o in state.get('alternatives',[])],
        'direct_ids':[r['id'] for r in state.get('results',[])+state.get('references',[])],
        'direct_scores':[r.get('score') for r in state.get('results',[])+state.get('references',[])]}
    return state


def restore_local(state, activities, *, as_of=None):
    # Deferred imports keep this new presentation boundary compatible with loaded modules.
    from services.dialogue import handle_turn
    from services.ai import empty_extraction
    from services.config import Settings
    state=deepcopy(state)
    if state.get('previous_local'):
        state['conditions']=deepcopy(state['previous_local']['conditions'])
        state['condition_modes']=deepcopy(state['previous_local'].get('condition_modes',{}))
        state['excluded_types']=list(state['previous_local'].get('excluded_types',[]))
    state.update(flow='program',search_scope={'kind':'local'},expanded=False,pending=None,code='restore_local')
    return handle_turn(state,'이전에 찾은 강서구 활동 다시 보기',activities,Settings(),
                       extraction=empty_extraction('search_program'),as_of=as_of)


def adjacent_programmes(activities, conditions, *, consent=False, as_of=None):
    allowed=list(NEIGHBOURS.get(district(conditions.get('region')),())) if consent else []
    covered=[];ranked=[]
    for region in allowed:
        rows=local_rows(activities,region)
        if not rows:continue
        covered.append(region)
        changed=dict(conditions,region=region)
        exact=recommend(rows,changed,as_of=as_of)
        options=programme_options(rows,changed,as_of=as_of)
        for row in exact['results']+exact['references']+[r for o in options for r in o['rows']]:
            if district(row['region']) not in allowed:continue
            item=deepcopy(row);item.update(score_program(row,conditions,as_of=as_of))
            item['available']=availability_status(row,as_of=as_of) in {'open','walk_in'}
            # Budget uncertainty must stay a reference even for an open registration.
            if row in exact['references'] or any(row in o['rows'] and not o['available'] for o in options):item['available']=False
            ranked.append(item)
    unique={row['id']:row for row in ranked}
    chosen=sorted(unique.values(),key=lambda row:(-row['score'],row['region'],row['id']))[:3]
    groups=[{'region':region,'rows':[row for row in chosen if district(row['region'])==region]} for region in covered]
    return {'districts':allowed,'covered':covered,'groups':[g for g in groups if g['rows']],
            'results':[row for row in chosen if row['available']],
            'references':[row for row in chosen if not row['available']]}

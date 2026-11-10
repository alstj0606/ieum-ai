"""Curated general ideas, never a facility directory or confirmed program inventory."""
from copy import deepcopy
import re
from services.activities import availability_status
from services.recommendations import STATUS_LABELS

IDEAS = [
    {'id':'walking','name':'가벼운 걷기','activity_type':'걷기','category':'체육','tags':['산책','야외','교류'],'near_home':False,'reason':'속도와 시간을 스스로 정하며 시작할 활동을 생각해 볼 수 있어요.'},
    {'id':'water','name':'수중운동','activity_type':'아쿠아로빅','category':'체육','tags':['물','수영'],'near_home':False,'reason':'물속에서 움직이는 활동에 관심이 있다면 살펴볼 수 있어요.'},
    {'id':'gym','name':'가벼운 체조','activity_type':'체조','category':'체육','tags':['실내','체조'],'near_home':True,'reason':'앉아서 하는 동작 등 원하는 방식의 체조를 알아볼 수 있어요.'},
    {'id':'golf','name':'파크골프','activity_type':'파크골프','category':'체육','tags':['야외','교류'],'near_home':False,'reason':'야외에서 함께 즐기는 활동이에요. 입문 교육과 이용 조건은 확인해야 해요.'},
    {'id':'swim','name':'수영 배우기','activity_type':'수영','category':'체육','tags':['물','배우기'],'near_home':False,'reason':'물을 익히고 싶다면 입문 강좌를 알아보는 방법이 있어요.'},
    {'id':'craft','name':'그림·만들기','activity_type':'미술','category':'문화·취미','tags':['실내','만들기','그림'],'near_home':True,'reason':'손으로 만들거나 그리는 데 관심이 있다면 생각해 볼 활동이에요.'},
    {'id':'garden','name':'식물 가꾸기','activity_type':'가드닝','category':'문화·취미','tags':['식물','만들기'],'near_home':True,'reason':'식물에 관심이 있다면 가꾸는 활동을 알아볼 수 있어요.'},
    {'id':'music','name':'공연 관람','activity_type':'국악공연','category':'문화·취미','tags':['공연','관람'],'near_home':False,'reason':'직접 운동하는 활동 외에 공연을 즐기는 방법도 있어요.'},
    {'id':'learning','name':'인문학 배우기','activity_type':'인문학','category':'평생학습','tags':['배우기','교류'],'near_home':True,'reason':'새로운 주제를 배우며 생각을 나누는 활동을 알아볼 수 있어요.'},
]


def suggestions(conditions, *, previous=()):
    candidates = [x for x in IDEAS if (not conditions.get('category') or x['category']==conditions['category']) and x['activity_type'] not in conditions.get('_excluded_types',[])]
    if conditions.get('mobility') in {'이동 적게','가까운 곳'}:
        candidates = [x for x in candidates if x['near_home']]
    interests=set(conditions.get('tags') or [])
    related={'수영':{'아쿠아로빅','체조'},'아쿠아로빅':{'수영','체조'},'슬로우조깅':{'걷기','체조'},'숲체험':{'걷기','가드닝'},'미술':{'가드닝','국악공연'}}
    def score(x):
        return (0 if x['id'] in previous else 1,
                5*(x['activity_type']==conditions.get('activity_type'))+3*(x['activity_type'] in related.get(conditions.get('activity_type'),set()))+len(interests & set(x['tags']))+
                (2 if conditions.get('budget_amount')==0 and x['id'] in {'walking','gym'} else 0)+
                (2 if conditions.get('purpose')=='교류' and '교류' in x['tags'] else 0))
    ranked=sorted(candidates,key=score,reverse=True)
    if not conditions.get('category') and not conditions.get('activity_type'):
        varied=[]
        for item in ranked:
            if item['category'] not in {x['category'] for x in varied}:varied.append(item)
        ranked=varied+[x for x in ranked if x not in varied]
    result=deepcopy(ranked[:3])
    for row in result:
        if interests & set(row['tags']):
            row['reason']='말씀하신 관심사와 연결되는 활동이에요. '+row['reason']
        if conditions.get('mobility') in {'이동 적게','가까운 곳'}:
            row['reason']+=' 이동을 줄이는 방식을 우선 제안하지만 실제 거리·접근성은 확인이 필요해요.'
    return result


def route_intent(text, request, state):
    compact=re.sub(r'\s+','',text)
    intent=request['intent']
    if intent in {'apply','yes','no','reset','change_time','change_activity'}:
        return intent
    if re.search(r'다른(?:운동|취미)',compact):return 'recommend_activity'
    if intent=='change_condition' or ('말고' in compact and request['update_fields']):
        return 'change_condition'
    if any(word in compact for word in ('배우','배워','강좌','수업','프로그램')):
        return 'search_program'
    if any(word in compact for word in ('수영장','체육관','시설','센터찾')) or intent=='find_facility':
        return 'find_facility'
    if ('아이디어' in compact or '추천' in compact or re.search(r'할수있는(?:활동|운동|취미)',compact) or intent=='recommend_activity'):
        return 'recommend_activity'
    if intent=='search_program':
        return intent
    if state.get('flow')=='ideas' and not request['conditions'].get('activity_type'):
        return 'recommend_activity'
    if state.get('flow')=='facility' and not request['conditions'].get('activity_type'):
        return 'find_facility'
    return intent


REGION_SCOPES = {"seoul-gangseo": {"강서구","서울강서구","서울특별시강서구","서울"}}


def supported_region(region):
    compact=(region or '').replace(' ','')
    return any(compact in aliases for aliases in REGION_SCOPES.values())


def facility_references(activities, conditions, *, as_of=None):
    """Derive only facilities explicitly named by verified activity records; no live lookup."""
    target=conditions.get('activity_type')
    kinds={'수영','아쿠아로빅'} if target=='수영' else {target} if target else None
    rows=[];seen=set()
    for item in activities:
        if item['is_demo'] or not item['facility_name'] or (kinds and item['activity_type'] not in kinds):
            continue
        if conditions.get('region') and conditions['region'].replace(' ','') not in item['region'].replace(' ',''):
            continue
        if not kinds and conditions.get('category') and item['category']!=conditions['category']:
            continue
        key=(item['facility_name'],item['address'])
        if key in seen:continue
        seen.add(key)
        rows.append({'name':item['facility_name'],'address':item['address'],'source_url':item['source_url'],
                     'verified_at':item['verified_at'],'source_program':item['name'],
                     'source_status':STATUS_LABELS[availability_status(item,as_of=as_of)],
                     'note':'공식 프로그램 자료에 등장하는 시설이에요. 현재 시설 운영·거리·요금·강좌 유무는 별도 확인이 필요해요.'})
    return rows[:3]

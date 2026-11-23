"""Button navigation over the same dialogue state, never a second recommendation store."""
from copy import deepcopy
import re

INTERESTS={
 '운동':'운동 프로그램을 찾아주세요',
 '취미':'취미 프로그램을 찾아주세요',
 '문화':'문화 공연을 보고 싶어요',
 '배움':'교육 프로그램을 찾아주세요',
 '사람 만나기':'사람들과 함께하는 프로그램을 찾아주세요',
}
# Administrative choices only, not a claim that programme data exists there.
REGIONS={'서울':('강서구','양천구','마포구'),'창원':('성산구','의창구'),'부산':('강서구','북구'),'부천':('원미구','소사구','오정구')}

def verified_dong(row):
    match=re.search(r'(?:^|[\s(])([가-힣]{2,10}\d{0,2}동)(?=[\s)\d]|$)',row.get('address') or '')
    return match.group(1) if match else None

def dong_options(activities,city,area):
    return sorted({verified_dong(r) for r in activities if city in r['region'] and area in r['region'] and verified_dong(r)})

def _step(state,label,message,picker):
    result=deepcopy(state)
    result.update(picker=picker,message=message,code='question',pending='region' if picker['stage'].startswith('region') else 'activity_type',
                  results=[],references=[],alternatives=[],ideas=[],facilities=[],selected_id=None,detail_focus=False,helper_focus=False,error=None)
    result.pop('recommendation_context',None);result.pop('application_helper',None);result.pop('web',None)
    result['history']=(result.get('history',[])+[{'role':'user','content':label},{'role':'assistant','content':message}])[-20:]
    return result

def open_picker(state,stage):
    prompts={'activity':'어떤 활동을 해보고 싶으세요?', 'condition':'무엇을 다시 선택할까요?', 'region_city':'어느 시에서 찾아볼까요? 다른 시는 직접 입력할 수 있어요.'}
    if stage not in prompts:raise ValueError('unknown navigation stage')
    return _step(state,'다시 선택' if stage=='condition' else '지역 다시 선택' if stage=='region_city' else '활동 다시 선택',prompts[stage],{'stage':stage})

def choose_city(state,city):
    if city not in REGIONS:raise ValueError('unknown city')
    result=_step(state,city,city+'의 어느 구에서 찾아볼까요?',{'stage':'region_district','city':city})
    if result.get('life_mode'):
        result['conditions']['region']=city;result['conditions'].pop('neighbourhood',None)
        result['location']=dict(city=city,district=None,neighbourhood=None)
    return result

def choose_district(state,area,activities,settings):
    city=(state.get('picker') or {}).get('city')
    if city not in REGIONS or area not in REGIONS[city]:raise ValueError('unknown district')
    if not any(city in r['region'] and area in r['region'] for r in activities):
        return choose_area(state,city,area,None,activities,settings)
    result=_step(state,area,'어느 동에서 찾아볼까요? 동을 모르시면 구 전체를 선택해도 괜찮아요.',{'stage':'region_dong','city':city,'district':area})
    if result.get('life_mode'):
        result['conditions']['region']=city+' '+area;result['conditions'].pop('neighbourhood',None)
        result['location']=dict(city=city,district=area,neighbourhood=None)
    return result

def choose_area(state,city,area,dong,activities,settings):
    if city not in REGIONS or area not in REGIONS[city]:raise ValueError('unknown region')
    if dong and dong not in dong_options(activities,city,area):raise ValueError('unverified neighbourhood')
    from services.discovery import discovery_turn
    from services.dialogue import basic_extract
    result=deepcopy(state);result.pop('picker',None)
    text=city+' '+area+(' '+dong if dong else '')+'에서 찾아주세요'
    return discovery_turn(result,text,activities,settings,extraction=basic_extract(text,result))[0]

def choose_interest(state,label,activities,settings):
    if label not in INTERESTS:raise ValueError('unknown interest')
    from services.discovery import discovery_turn
    from services.dialogue import basic_extract
    result=deepcopy(state);result.pop('picker',None)
    # Reset only activity-specific filters; preserve region, time, budget and age.
    for key in ('activity_type','category','tags','beginner','purpose'):result['conditions'].pop(key,None)
    result['flow']='program';result['pending']=None
    text=INTERESTS[label]
    return discovery_turn(result,text,activities,settings,extraction=basic_extract(text,result))[0]

def contextual_text(state,text):
    picker=state.get('picker') or {}
    compact=re.sub(r'\s+','',text).rstrip('.!?')
    if picker.get('stage')=='region_dong' and compact in {'상관없어요','동은상관없어요','동네는상관없어요','구전체','전체'}:
        return picker['city']+' '+picker['district']+' 전체에서 찾아주세요'
    if picker.get('stage')=='region_dong' and re.search(r'오전|오후|저녁|무료|\d+\s*원',text) and not re.search(r'[가-힣]+구',text):
        return picker['city']+' '+picker['district']+' '+text
    if picker.get('city') and re.search(r'[가-힣]+\d{0,2}(?:구|동)(?:요|에서|\s|$)',text) and not any(city in text for city in REGIONS):
        return picker['city']+' '+(picker.get('district','')+' ' if '구' not in text else '')+text
    return text

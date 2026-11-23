"""Web search state shares conditions/history with legacy conversation, not facts."""
from copy import deepcopy
import re
from services.web_search import search_programs,SearchError,ERRORS,official_hosts
from services.neighbourhood import location_from,question,location_label


def message(state,text,answer,code='web',pending=None):
 state=deepcopy(state);state.update(message=answer,code=code,pending=pending,error=None,detail_focus=False,helper_focus=False,
  results=[],references=[],alternatives=[],ideas=[],facilities=[])
 state['history']=(state.get('history',[])+[{'role':'user','content':text},{'role':'assistant','content':answer}])[-20:]
 state.pop('recommendation_update',None)
 return state

def selected(state):
 web=state.get('web') or {}
 return next((r for r in web.get('rows',[]) if r['id']==web.get('selected_id')),None)

def select_web(state,activity_id):
 state=deepcopy(state);row=next((r for r in state.get('web',{}).get('rows',[]) if r['id']==activity_id),None)
 if not row:raise ValueError('visible programme required')
 state=message(state,'선택한 프로그램 자세히 보기','선택한 공식 프로그램이에요. 모집 상태와 확인 시각을 살펴봐 주세요.','web_detail')
 state['web']['selected_id']=activity_id
 return state

def search(state,settings,activities,*,expanded=False,transport=None):
 state=deepcopy(state);state.pop('cache_only',None);state.pop('search_failure',None);previous=state.get('web') or {}
 try:outcome=search_programs(settings,state['location'],state['conditions'],hosts=official_hosts(activities),excluded=previous.get('excluded',[]),expanded=expanded,transport=transport)
 except SearchError as error:
  result=cache_search(state,activities)
  result['search_failure']={'code':error.code,'message':ERRORS[error.code]}
  result['message']=ERRORS[error.code]+' '+result['message']
  return result
 outcome.update(selected_id=None,excluded=previous.get('excluded',[]));state['web']=outcome
 count=len(outcome['rows'])
 answer=f'공식 페이지에서 프로그램 {count}개를 확인했어요. 현재 신청 여부는 각 카드에서 확인해 주세요.' if count else ERRORS.get(outcome['status'],ERRORS['unverified'])
 if expanded:answer+=' 동의하신 확대 검색 결과예요. 장소가 요청 동네와 다르면 따로 표시해요.'
 return message(state,'인터넷에서 찾기',answer,'web',None if count else 'web_expand')

def before_turn(state,text,settings,activities,**kwargs):
 if not state.get('web') or state['web']['status']=='not_configured':return None
 compact=re.sub(r'\s+','',text).rstrip('.!?')
 if state.get('pending')=='web_expand' and compact in {'네','예','다른동네도괜찮아요','네,다른동네도찾아주세요'}:
  result=deepcopy(state);web=result['web'];web['excluded']=list(dict.fromkeys(web.get('excluded',[])+[r['id'] for r in web.get('rows',[])]))
  return search(result,settings,activities,expanded=True,**kwargs)
 if compact in {'다른동네도괜찮아요','인접지역도찾아줘','좀더넓게찾아줘'}:
  return message(state,text,'입력하신 동네 밖의 공식 자료도 찾아볼까요? 동의하셔야 범위를 넓혀요.','web','web_expand')
 if compact in {'아니요,이동네만볼게요','이동네만볼게요'} and state.get('pending')=='web_expand':
  return message(state,text,'이 동네 조건을 유지했어요. 활동이나 시간을 바꿔볼까요?','web')
 if compact in {'이건별로예요','마음에안들어요','다른거추천해줘','다른추천보기','다른활동보기'}:
  result=deepcopy(state);web=result['web'];ids=[web['selected_id']] if web.get('selected_id') else [r['id'] for r in web['rows']]
  web['excluded']=list(dict.fromkeys(web.get('excluded',[])+ids))
  return search(result,settings,activities,expanded=web.get('expanded',False),**kwargs)
 if compact in {'다시검색','인터넷검색다시하기','좀더가까운곳','더가까운곳'}:
  if '가까운' in compact and not state.get('location',{}).get('neighbourhood'):
   result=message(state,text,'어느 동 근처가 좋으세요? 거리는 임의로 계산하지 않아요.','question','web_dong');result.pop('web',None)
   return result
  return search(state,settings,activities,expanded=False,**kwargs)
 rows=state['web'].get('rows',[])
 number=re.fullmatch(r'([123])번',compact)
 if number and int(number.group(1))>len(rows):return message(state,text,'화면에 있는 프로그램 번호를 다시 골라주세요.','web','web_selection')
 if compact in {'좋아요','네','신청방법알려줘','신청방법알려주세요','신청하고싶어요','이거어떻게신청해','이거어떻게신청해요','이활동신청방법','참여방법알려줘'} or number:
  row=rows[int(number.group(1))-1] if number and int(number.group(1))<=len(rows) else selected(state) or (rows[0] if len(rows)==1 else None)
  if row:return select_web(state,row['id'])
  if rows:return message(state,text,'마음에 드는 프로그램의 자세히 보기를 눌러주세요.','web')
 return None

def after_turn(state,previous,text,settings,activities,**kwargs):
 if not previous.get('web_enabled') and not settings.search_configured:return state
 if state['code']=='start':return state
 result=deepcopy(state);result['web_enabled']=True
 if result.get('picker'):return result
 location=location_from(result['conditions'],text,previous.get('location'))
 if previous.get('pending') in {'web_location','web_dong'} and not location.get('neighbourhood'):
  location['neighbourhood']=previous.get('location',{}).get('neighbourhood')
 if location.get('neighbourhood'):result['conditions']['neighbourhood']=location['neighbourhood']
 result['location']=location
 has_activity=bool(result['conditions'].get('activity_type') or result['conditions'].get('category') or result['conditions'].get('purpose'))
 if result.get('pending') in {'activity_type','time_slot','effort_preference','budget_unit'}:
  result.pop('web',None);result.update(results=[],references=[],alternatives=[],ideas=[],facilities=[],selected_id=None)
  return result
 if not has_activity:return result
 if question(location) and (location.get('neighbourhood') or result['conditions'].get('region')):
  result.pop('web',None)
  return message(result,text,question(location),'question','web_location')
 if not location.get('city'):
  result['message']='어느 시·구·동에서 찾아볼까요? 자세한 집 주소는 필요하지 않아요.'
  return result
 if result.get('pending') in {'budget_unit','activity_type','time_slot','effort_preference'}:return result
 if not settings.search_configured:
  cached=result;cached['cache_only']=True;cached['search_failure']={'code':'not_configured','message':ERRORS['not_configured']}
  cached['message']=ERRORS['not_configured']+' '+cached['message']
  return cached
 return search(result,settings,activities,**kwargs)


def cache_search(state,activities):
 """Explicit fallback retains region/filters; never silently substitutes Gangseo."""
 from services.dialogue import handle_turn
 from services.ai import empty_extraction
 from services.config import Settings
 result=deepcopy(state);result.pop('web',None);result.pop('recommendation_context',None)
 result.update(selected_id=None,helper_focus=False,detail_focus=False,cache_only=True)
 result=handle_turn(result,'같은 조건으로 저장 자료를 찾아줘',activities,Settings(),extraction=empty_extraction('search_program'))
 result.pop('recommendation_update',None)
 from services.discovery import visible_activities
 if result.get('pending')=='expand_region' and visible_activities(result):result['pending']=None
 result['message']='저장 자료만 확인했어요. 인터넷 검색 결과가 아니에요. '+result['message']
 result['notice']='기존 자료의 확인일과 모집 상태를 확인해 주세요. 현재 정보를 새로 확인한 것은 아니에요.'
 return result

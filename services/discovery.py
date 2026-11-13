"""User-first orchestration over the existing intent/search/application services."""
from copy import deepcopy
import re
from services.dialogue import handle_turn,basic_extract,choose_alternative
from services.activity_catalog import catalog_entry
from services.ai import AIError,empty_extraction

EXAMPLES=('수영을 배우고 싶어요','가볍게 운동하고 싶어요','새로운 취미를 찾고 싶어요','사람들과 함께하는 활동이 좋아요')
HEALTH=re.compile(r'무릎|허리|관절|통증|질환|진단|당뇨|혈압|심장|수술|건강|아프|불편|휠체어|장애|병원')
PRIVATE=re.compile(r'(?<!\d)\d{6,}(?!\d)(?!\s*원)|(?:비밀번호|인증번호|주민등록번호)\s*[:=는은]\s*\S+|아이디\s*[:=]\s*\S+')


def safe_input(text,state):
    if PRIVATE.search(text):return '개인정보가 포함될 수 있는 입력은 저장하지 않았어요.',False,True
    if not HEALTH.search(text):return text,False,False
    # Keep only validated non-medical slots, not a body part, diagnosis or raw sentence.
    try:request=basic_extract(text,state)
    except AIError:request=empty_extraction()
    values=request['conditions']
    pieces=[str(values[k]) for k in ('region','activity_type','category','time_slot','purpose','companionship','effort_preference','mobility') if values.get(k)]
    pieces.extend(day+'요일' for day in values.get('weekdays') or [])
    if values.get('age') is not None:pieces.append(str(values['age'])+'세')
    if values.get('budget_amount') is not None:pieces.append(str(values['budget_amount'])+'원')
    if values.get('budget_unit'):pieces.append(values['budget_unit'])
    if values.get('beginner') is True:pieces.append('초보')
    return ' '.join(pieces+['신체활동 부담 확인을 원해요.']),True,False


def discovery_turn(state,text,activities,settings,**kwargs):
    state=deepcopy(state);state['discovery_mode']=True
    safe,caution,blocked=safe_input(text,state)
    if blocked:
        state.update(error='개인정보·비밀번호·인증번호는 입력하지 마세요. 공식 사이트에서만 직접 입력해 주세요.')
        return state,safe
    if caution:state['conditions']['movement_caution']='부담 확인'
    result=handle_turn(state,safe,activities,settings,**kwargs)
    result['discovery_mode']=True
    regions='·'.join(sorted({r['region'] for r in activities if not r['is_demo']})) or '확인된 지역 없음'
    if result.get('pending')=='region':result['message']='어느 지역에서 찾아볼까요? 현재 보유한 프로그램 지역은 '+regions+'예요.'
    if not result['conditions'].get('activity_type') and not result['conditions'].get('category') and any(w in safe for w in ('새로운','뭔가','새롭게')):
        result.update(results=[],references=[],alternatives=[],ideas=[],pending='activity_type',code='question',message='어떤 활동이 끌리세요? 만들기, 운동, 문화 체험 중 하나를 골라도 좋아요.')
    if result['code']=='unsupported_region':
        result['message']=f'요청하신 지역의 프로그램 자료는 아직 없어요. 보유 자료는 {regions} {len(activities)}건이며 실시간 검색은 하지 않아요. 지역을 바꾸거나 일반 활동 아이디어를 살펴볼까요?'
    if caution:
        result['notice']='건강 관련 상세 표현은 저장하지 않고 신체 부담 확인 요청만 기억해요. 운동의 안전 여부를 판단하지 않으며 우려가 있으면 의료진과 상담해 주세요.'
    if result.get('history') and result['history'][-1].get('role')=='assistant':
        result['history'][-1]['content']=result['message']
    return result,safe


def visible_activities(state):
    """At most three unique official records, direct candidates before explicit alternatives."""
    rows=[];seen=set()
    for row in state.get('results',[])+state.get('references',[]):
        if not row.get('is_demo') and row['id'] not in seen:
            rows.append(dict(row,requires_confirmation=any(r['id']==row['id'] for r in state.get('references',[])),match_label=row.get('match_label') or '조건으로 찾은 공식 자료'));seen.add(row['id'])
    for option in state.get('alternatives',[]):
        for row in option['rows']:
            if not row.get('is_demo') and row['id'] not in seen:
                rows.append(dict(row,requires_confirmation=not option.get('available',False),reason=option['reason'],match_label=option.get('match_label','대안 활동')));seen.add(row['id'])
    return rows[:3]


def select_activity(state,activity_id,activities,settings,**kwargs):
    row=next((r for r in visible_activities(state) if r['id']==activity_id),None)
    if row is None:raise ValueError('현재 표시된 공식 활동을 선택해 주세요.')
    state=deepcopy(state)
    if activity_id not in {r['id'] for r in state['results']+state['references']}:
        state=choose_alternative(state,row['activity_type'],activities,settings,**kwargs)
    if activity_id in {r['id'] for r in state['results']+state['references']}:state['selected_id']=activity_id
    return state


def institution_for_selection(state,activities):
    allowed={r['id'] for r in state.get('results',[])+state.get('references',[])}
    selected=state.get('selected_id')
    row=next((r for r in activities if r['id']==selected and selected in allowed and not r['is_demo']),None)
    return row.get('institution_id') if row else None


def public_card(row,*,as_of=None):
    return catalog_entry(row,as_of=as_of)

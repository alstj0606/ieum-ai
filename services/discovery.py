"""User-first orchestration over the existing intent/search/application services."""
from copy import deepcopy
import re
from services.dialogue import handle_turn,basic_extract,choose_alternative,new_state
from services.activity_catalog import catalog_entry
from services.ai import AIError,empty_extraction

EXAMPLES=('수영을 배우고 싶어요','문화 행사를 보고 싶어요','새로운 취미를 찾고 싶어요','교육 프로그램을 찾고 싶어요')
HEALTH=re.compile(r'무릎|허리|관절|통증|질환|진단|당뇨|혈압|심장|수술|건강|아프|불편|휠체어|장애|병원')
PRIVATE=re.compile(r'(?<!\d)\d{6,}(?!\d)(?!\s*원)|(?:비밀번호|인증번호|주민등록번호)\s*[:=는은]\s*\S+|아이디\s*[:=]\s*\S+')


def available_records(state, activities):
    """Session refusals apply at both search and rendering boundaries."""
    declined=set(state.get('declined_ids',[]))
    return [row for row in activities if row['id'] not in declined]


def _answer(state,text,message,code,pending=None):
    state.update(message=message,code=code,pending=pending,error=None,detail_focus=False,helper_focus=False)
    state['history']=(state.get('history',[])+[{'role':'user','content':text},{'role':'assistant','content':message}])[-20:]
    return state


def return_to_recommendations(state):
    previous=state.get('recommendation_context')
    result=deepcopy(previous or state)
    result['history']=deepcopy(state.get('history',[]))
    result.pop('recommendation_context',None)
    result.pop('application_helper',None)
    result.update(selected_id=None,helper_focus=False,detail_focus=False)
    result.pop('recommendation_update',None)
    return _answer(result,'추천으로 돌아가기','앞서 찾은 활동이에요. 다른 활동을 고르거나 조건을 바꿀 수 있어요.','recommendations')


def _decision(state,text,activities,settings,kwargs):
    """Explicit accept/refuse commands never invent facts or silently widen region."""
    compact=re.sub(r'\s+','',text).rstrip('.!?')
    if state.get('pending')=='expand_region':return None
    if state.get('pending')=='refine':
        questions={'시간':('오전, 오후, 저녁 중 언제로 바꿔볼까요?','time_slot'),
                   '활동':('어떤 활동으로 바꿔볼까요? 운동, 만들기, 공연처럼 말씀해 주세요.','activity_type'),
                   '지역':('어느 지역으로 바꿔볼까요? 저장된 공식 자료가 있는 지역만 안내할 수 있어요.','region')}
        if compact in questions:
            message,pending=questions[compact]
            return _answer(state,text,message,'question',pending)
    if compact in {'뒤로','이전추천','추천으로돌아가기'} and state.get('recommendation_context'):
        return return_to_recommendations(state)
    options=visible_activities(state)
    declined=bool(re.fullmatch(r'(?:다른(?:거|것|프로그램|추천)(?:도)?(?:추천)?(?:해줘|해주세요|보여줘)?|마음에안들(?:어|어요)|싫어(?:요)?|아니요)',compact))
    if declined and state.get('ideas') and not options:
        from services.activity_guidance import suggestions
        from services.personalization import profile_conditions
        excluded=set(state.get('declined_idea_ids',[]))|{x['id'] for x in state['ideas']}
        state['declined_idea_ids']=sorted(excluded)
        state['ideas']=[x for x in suggestions(profile_conditions(state),previous=excluded) if x['id'] not in excluded]
        message='다른 일반 활동 아이디어예요. 실제 모집 프로그램은 아니며, 관심 활동을 고르면 공식 자료를 찾아볼게요.' if state['ideas'] else '새로 제안할 활동이 부족해요. 활동 종류와 시간 중 무엇을 바꿔볼까요?'
        return _answer(state,text,message,'ideas' if state['ideas'] else 'refine',None if state['ideas'] else 'refine')
    if declined and (options or state.get('declined_ids')):
        selected=state.get('selected_id')
        ids=[r['id'] for r in options if not selected or r['id']==selected]
        state['declined_ids']=list(dict.fromkeys(state.get('declined_ids',[])+ids))
        state.pop('recommendation_context',None)
        state.pop('application_helper',None)
        state.update(selected_id=None,detail_focus=False,helper_focus=False)
        remaining=available_records(state,activities)
        command='같은 조건으로 찾아줘'
        result=handle_turn(state,command,remaining,settings,as_of=kwargs.get('as_of'),extraction=basic_extract(command,state))
        result['declined_ids']=state['declined_ids']
        result['history']=(state.get('history',[])+[{'role':'user','content':text}])[-19:]
        if visible_activities(result):
            message='앞서 보여드린 활동은 제외했어요. 같은 지역과 조건에서 다른 공식 자료를 살펴볼게요.'
            pending=None
        else:
            result.update(results=[],references=[],alternatives=[],ideas=[],facilities=[])
            message='앞서 보여드린 활동을 제외하면 같은 조건의 다른 공식 자료가 부족해요. 활동 종류와 시간 중 무엇을 바꿔볼까요?'
            pending='refine'
        if state.get('diagnostic'):result['diagnostic']=deepcopy(state['diagnostic'])
        result['mode']=state.get('mode','basic');result['notice']=state.get('notice')
        result.update(message=message,code='alternatives' if pending is None else 'refine',pending=pending)
        result['history'].append({'role':'assistant','content':message})
        result.pop('recommendation_update',None)
        return result
    number=re.fullmatch(r'(?:제)?([123])번(?:으로|이요|좋아요)?',compact)
    if number and int(number.group(1))>len(options):return _answer(state,text,'화면에 나온 활동 번호를 다시 골라주세요.','choose','selection')
    accept=compact in {'네','예','좋아요','이걸로할게요','이게좋아요','마음에들어요','선택할게요'}
    if state.get('helper_focus') and accept and not number:
        # Acknowledging an instruction is neither a new selection nor proof of
        # an external application. Keep the current programme and guide step.
        state['history']=(state.get('history',[])+[{'role':'user','content':text},{'role':'assistant','content':state['message']}])[-20:]
        return state
    if options and (accept or number):
        selected=next((r for r in options if r['id']==state.get('selected_id')),None)
        row=options[int(number.group(1))-1] if number and int(number.group(1))<=len(options) else selected or (options[0] if len(options)==1 else None)
        if row is None:return _answer(state,text,'어떤 활동이 마음에 드세요? 아래 활동의 자세히 보기를 눌러주세요.','choose','selection')
        result=select_activity(state,row['id'],available_records(state,activities),settings,as_of=kwargs.get('as_of'))
        result=_answer(result,text,'선택한 활동의 상세 정보예요. 신청 가능 여부는 공식 안내에서 확인해 주세요.','detail')
        result['detail_focus']=True
        return result
    return None


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
    if re.sub(r'\s+','',safe).rstrip('.!?') in {'처음부터다시','처음부터다시찾기','처음부터','새로시작','초기화','대화초기화'}:
        return dict(new_state(),discovery_mode=True),safe
    if caution:state['conditions']['movement_caution']='부담 확인'
    decision=_decision(state,safe,activities,settings,kwargs)
    if decision is not None:return decision,safe
    state['detail_focus']=False
    result=handle_turn(state,safe,available_records(state,activities),settings,**kwargs)
    result['discovery_mode']=True
    # A parent recommendation snapshot is navigation, not an undo of conditions.
    # Once a new search condition changes, use the new candidates on return.
    if result['conditions']!=state['conditions']:
        result.pop('recommendation_context',None)
    regions='·'.join(sorted({r['region'] for r in activities if not r['is_demo']})) or '확인된 지역 없음'
    if result.get('pending')=='region':result['message']='어느 지역에서 찾아볼까요? 현재 보유한 프로그램 지역은 '+regions+'예요.'
    if not result['conditions'].get('activity_type') and not result['conditions'].get('category') and any(w in safe for w in ('새로운','뭔가','새롭게')):
        result.update(results=[],references=[],alternatives=[],ideas=[],pending='activity_type',code='question',message='어떤 활동이 끌리세요? 만들기, 운동, 문화 체험 중 하나를 골라도 좋아요.')
    if result['code']=='unsupported_region':
        result['message']=f'요청하신 지역의 프로그램 자료는 아직 없어요. 보유 자료는 {regions} {len(activities)}건이며 실시간 검색은 하지 않아요. 지역을 바꾸거나 일반 활동 아이디어를 살펴볼까요?'
    if result.get('pending')=='expand_region' and visible_activities(result):
        # A visible alternative and a simultaneous yes/no expansion question are
        # ambiguous: "좋아요" must select a sole card, not grant regional consent.
        result['pending']=None
        result['message']='정확히 일치하는 신청 가능한 프로그램은 확인하지 못했어요. 같은 지역에서 확인한 유사·대안 활동이에요. 모집 상태를 확인해 주세요.'
    if caution:
        result['notice']='건강 관련 상세 표현은 저장하지 않고 신체 부담 확인 요청만 기억해요. 운동의 안전 여부를 판단하지 않으며 우려가 있으면 의료진과 상담해 주세요.'
    if result.get('history') and result['history'][-1].get('role')=='assistant':
        result['history'][-1]['content']=result['message']
    return result,safe


def visible_activities(state):
    """At most three unique official records, direct candidates before explicit alternatives."""
    rows=[];seen=set(state.get('declined_ids',[]))
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
    context=deepcopy(state)
    context.pop('recommendation_context',None)
    context.pop('application_helper',None)
    if activity_id not in {r['id'] for r in state['results']+state['references']}:
        state=choose_alternative(state,row['activity_type'],activities,settings,**kwargs)
    if activity_id in {r['id'] for r in state['results']+state['references']}:state['selected_id']=activity_id
    state['recommendation_context']=context
    return state


def institution_for_selection(state,activities):
    allowed={r['id'] for r in state.get('results',[])+state.get('references',[])}
    selected=state.get('selected_id')
    row=next((r for r in activities if r['id']==selected and selected in allowed and not r['is_demo']),None)
    return row.get('institution_id') if row else None


def public_card(row,*,as_of=None):
    return catalog_entry(row,as_of=as_of)

"""Session conversation policy, independent of search transport and verified facts."""
from copy import deepcopy
import logging
import re
from services.ai import AIError, validate_extraction
from services.dialogue import basic_extract, new_state
from services.activity_guidance import IDEAS, suggestions
from services.neighbourhood import location_from, location_label, question
from services.personalization import update_modes, profile_conditions
from services.recommendation_pipeline import anchor_request
from services import conversation_ai

LOG=logging.getLogger(__name__)
GENERAL={'chat','explore','howto','home'}


def reply(state,text,answer,route,pending=None):
    state=deepcopy(state)
    state.update(message=answer,code='conversation',conversation_route=route,pending=pending,error=None,notice=None,
        results=[],references=[],alternatives=[],ideas=[],facilities=[],selected_id=None,detail_focus=False,helper_focus=False,flow='conversation')
    for key in ('web','recommendation_context','application_helper','recommendation_update','search_failure','cache_only'):state.pop(key,None)
    state['history']=(state.get('history',[])+[{'role':'user','content':text},{'role':'assistant','content':answer}])[-20:]
    return state


def rule_route(text,state,request):
    c=re.sub(r'\s+','',text).rstrip('.!?')
    if re.fullmatch(r'(안녕(?:하세요|하세용)?|반가워요|고마워(?:요)?|감사(?:해요|합니다)|잘가(?:요)?)',c):return 'chat'
    if any(x in c for x in ('돈많이안','저렴한활동')):return 'explore'
    if '집에서' in c and any(x in c for x in ('취미','활동','알려','할수','하고')):return 'home'
    if any(x in c for x in ('어떻게시작','처음배우려면','시작하는방법','시작방법','그리는방법')):return 'howto'
    if any(x in c for x in ('너무비싸','비싸요','너무멀','멀어요','다른거','다른것','마음에안','별로','아까추천')):return 'followup'
    if request['intent']=='change_activity':return 'explore'
    if request['conditions'].get('activity_type') or any(x in c for x in ('다시검색','검색다시','다시찾아','찾아','찾고','강습','강좌','배우고싶','배워보고싶','수영장','문화센터')):return 'search'
    if any(x in c for x in ('심심','뭘해야','모르겠','사람들','사람을','만나','취미','추천','뻐근','운동하고','무리하지','할만한')):return 'explore'
    if state.get('pending') in {'region','web_location','web_dong','life_budget'} and state.get('search_requested'):return 'search'
    if state.get('conversation_route') in {'search','followup'} and (request['update_fields'] or request['clear_fields']):return 'search'
    if request['conditions'].get('region') or request['conditions'].get('neighbourhood'):return 'chat'
    return state.get('conversation_route') if state.get('conversation_route') in GENERAL else 'explore'


def grounded_request(text,state,request):
    request=anchor_request(text,validate_extraction(deepcopy(request)))
    explicit=basic_extract(text,state)
    # A model must never supply a location inferred from history, inventory or 'nearby'.
    for field in ('region','neighbourhood','age','gender','residence'):
        if field in request['update_fields']:
            request['update_fields'].remove(field);request['conditions'][field]=None
        if field in explicit['update_fields']:
            request['update_fields'].append(field);request['conditions'][field]=explicit['conditions'][field]
    return request


def merge(state,text,request):
    state=deepcopy(state);old=dict(state['conditions']);update_modes(state,text,request)
    updates=request['update_fields'];values=request['conditions']
    if 'region' in updates and old.get('region')!=values['region'] and 'neighbourhood' not in updates:state['conditions'].pop('neighbourhood',None)
    if 'activity_type' in updates:
        for k in ('category','tags','beginner'):
            if k not in updates:state['conditions'].pop(k,None)
    for k in request['clear_fields']:state['conditions'].pop(k,None)
    if 'region' in request['clear_fields']:state['conditions'].pop('neighbourhood',None)
    for k in updates:state['conditions'][k]=values[k]
    state['any_fields']=list((set(state.get('any_fields',[]))|set(request['clear_fields']))-set(updates))
    state['location']=location_from(state['conditions'],text, None if 'region' in updates or 'region' in request['clear_fields'] else state.get('location'))
    # Keep the explicitly stated city with district; never resolve a dong via the inventory.
    loc=state['location']
    if loc.get('city'):
        state['conditions']['region']=' '.join(x for x in (loc['city'],loc['district']) if x)
    return state


def ideas_reply(state,text,route,plan):
    answer={'explore':'부담 없이 시작할 활동을 함께 골라봐요. 마음이 가는 게 있나요?',
        'home':'집에서는 그림 그리기나 식물 가꾸기부터 생각해 볼 수 있어요. 어떤 쪽이 끌리세요?',
        'howto':'처음에는 연필과 종이로 주변 물건 하나를 천천히 그려보세요. 근처에서 배울 곳도 찾아드릴까요?'}[route]
    if route=='howto' and state['conditions'].get('activity_type') not in {None,'미술'}:
        answer='처음에는 필요한 도구와 입문 방법부터 살펴보면 좋아요. 근처에서 배울 곳도 찾아드릴까요?'
    if plan and plan.get('reply'):
        answer=plan['reply']+(' 근처에서 배울 곳도 찾아드릴까요?' if route=='howto' else ' 어떤 활동이 끌리세요?')
    result=reply(state,text,answer,route)
    excluded=state.get('declined_idea_ids',[])
    pool=[deepcopy(x) for x in IDEAS if x['id'] not in excluded and (route!='home' or x['near_home'])]
    ids=plan.get('idea_ids',[]) if plan else []
    if route=='home':ids=['craft','garden','gym']
    if not ids:ids=[x['id'] for x in suggestions(profile_conditions(state),previous=excluded)]
    if any(x in text for x in ('만나','사람','교류')):ids=['walking','golf','learning']
    result['ideas']=[x for i in ids for x in pool if x['id']==i][:3] if route!='howto' else []
    return result


def public_search(state,settings,activities,*,as_of=None):
    from services.live_discovery import search, cache_search
    if settings.search_configured:result=search(state,settings,activities)
    else:
        result=cache_search(state,activities)
        result['search_failure']={'code':'not_configured'}
    return present_search(result,state,settings)


def present_search(result,state,settings):
    from services.discovery import visible_activities
    result['life_mode']=True;result['conversation_route']='search';result['search_requested']=True
    result['mode']=state.get('mode','basic');result['diagnostic']=state.get('diagnostic')
    result['notice']=None
    web=result.get('web') or {}
    rows=web.get('rows',[]) if web else visible_activities(result)
    failure=result.get('search_failure')
    if web:
        result['message']='활동을 찾았어요. 장소와 모집 상태를 확인해 주세요.' if rows else '아직 확인된 프로그램이 없어요. 다른 지역도 찾아볼까요?'
    elif rows:
        result['message']=('새 정보를 찾기 어려워 이전에 확인한 프로그램을 보여드려요.' if failure and failure['code']!='not_configured' else '이전에 확인한 프로그램이에요.')+' 신청 전 확인이 필요해요.'
    elif failure and failure['code']!='not_configured':result['message']='지금은 새로운 정보를 찾기 어려워요. 다시 찾아볼까요?'
    else:result['message']='아직 확인된 프로그램이 없어요. 다른 활동이나 지역으로 찾아볼까요?'
    if not rows and not web:result.update(results=[],references=[],alternatives=[],ideas=[],facilities=[],pending='life_refine')
    if failure:failure['message']='지금은 새로운 정보를 찾기 어려워요. 다시 찾아볼까요?'
    LOG.info('activity_search provider=%s outcome=%s cache=%s',settings.search_provider,
             failure['code'] if failure else web.get('status','saved'),bool(web.get('cache_hit')))
    return result


def turn(state,text,activities,settings,*,extraction=None,client=None,as_of=None):
    from services.discovery import safe_input, _decision, visible_activities
    from services.live_discovery import before_turn
    state=deepcopy(state);safe,caution,blocked=safe_input(text,state)
    if blocked:state['error']='개인정보는 공식 사이트에서만 입력해 주세요.';return state,safe
    if len(safe)>1500:state['error']='조금 짧게 말씀해 주세요.';return state,safe
    compact=re.sub(r'\s+','',safe).rstrip('.!?')
    if compact in {'처음부터','처음부터다시','처음부터다시찾기','처음으로돌아가기','새로시작','초기화','대화초기화'}:
        return dict(new_state(),life_mode=True,web_enabled=True),safe
    # Existing verified selection/application and consent logic runs before free conversation.
    if state.get('helper_focus') and state.get('application_helper') and compact in {'다음단계','이전단계','다시설명'}:
        from services.dialogue import handle_turn
        return handle_turn(state,safe,activities,settings,extraction=basic_extract(safe,state),as_of=as_of),safe
    if not state.get('web') and compact in {'인접지역도찾아줘','인접지역도확인','다른동네도괜찮아요'}:
        result=reply(state,safe,'다른 동네까지 넓혀서 찾아볼까요?','search','expand_region');result['search_requested']=True
        return result,safe
    if not state.get('web') and state.get('pending')=='expand_region' and compact in {'네','예','좋아요','인접지역도확인','아니요','이지역만볼게요'}:
        if compact in {'아니요','이지역만볼게요'}:return reply(state,safe,'지역을 넓히지 않을게요. 다른 활동을 골라볼까요?','search','life_refine'),safe
        if settings.search_configured:
            from services.live_discovery import search
            result=search(state,settings,activities,expanded=True)
            result['message']='다른 동네에서 찾은 활동이에요.' if result.get('web',{}).get('rows') else '아직 확인된 인접 지역 프로그램이 없어요.'
            return result,safe
        from services.dialogue import handle_turn
        from services.ai import empty_extraction
        from services.config import Settings
        result=handle_turn(state,'네',activities,Settings(),extraction=empty_extraction('yes'),as_of=as_of)
        result['message']='이전에 확인한 인접 지역 프로그램이에요. 신청 전 확인이 필요해요.' if visible_activities(result) else '아직 확인된 인접 지역 프로그램이 없어요.'
        result['life_mode']=True;result['conversation_route']='search'
        return result,safe
    action=before_turn(state,safe,settings,activities)
    if action is not None:
        action['life_mode']=True;action['notice']=None
        return action,safe
    if '신청' in compact and (visible_activities(state) or state.get('web',{}).get('rows')):
        if state.get('web'):
            from services.live_discovery import selected, select_web
            row=selected(state) or (state['web']['rows'][0] if len(state['web']['rows'])==1 else None)
            if row:return select_web(state,row['id']),safe
        else:
            from services.dialogue import application_guide
            result=application_guide(state,activities,as_of=as_of)
            result['message']='확인된 신청 방법을 안내할게요. 문의 전화가 있어도 전화 접수가 가능한지는 따로 확인해야 해요.'
            return result,safe
    if compact in {'네','예','좋아요','신청방법알려줘','이거어떻게신청해','전화로신청할수있어'} or re.fullmatch('[123]번',compact):
        action=_decision(state,safe,activities,settings,{'as_of':as_of})
        if action is not None:return action,safe
        if compact in {'네','예','좋아요'} and state.get('conversation_route')=='howto':
            state.update(search_requested=True,conversation_route='search',pending='region')
    if compact in {'다른시간','다른시간찾기','다른시간에요'}:
        result=reply(state,safe,'오전, 오후, 저녁 중 언제가 편하세요?','search','time_slot');result['search_requested']=True
        return result,safe
    plan=None
    try:
        if extraction is not None:request=extraction;mode='basic';diagnostic=None
        elif settings.gemini_api_key:
            plan=conversation_ai.understand(safe,state,activities,settings,client=client);request=plan['extraction'];mode='gemini';diagnostic=None
        else:raise AIError(code='key_missing')
    except AIError as error:
        request=basic_extract(safe,state);mode='fallback';diagnostic={'code':error.code}
        LOG.info('conversation_fallback code=%s',error.code)
    request=grounded_request(safe,state,request)
    old=deepcopy(state);state=merge(state,safe,request)
    state.update(mode=mode,diagnostic=diagnostic,notice=None,life_mode=True)
    route=rule_route(safe,old,request)
    # Explicit local controls override ambiguous model routing; model handles open language.
    explicit_search=any(w in compact for w in ('찾아','찾고','어디서','근처','배우고싶','배워보고싶'))
    waiting=old.get('pending') in {'region','web_location','web_dong','life_budget','time_slot'} and old.get('search_requested')
    if plan and route not in {'chat','followup','home'} and not explicit_search and not waiting:
        route=plan['route']
    if caution:state['conditions']['movement_caution']='부담 확인'
    if any(w in compact for w in ('시간은상관없','오후','오전','무료로')) and old.get('conversation_route') in {'howto','explore','home'} and route!='search':
        route=old['conversation_route']
    if route=='chat':
        answer='안녕하세요. 해보고 싶은 일이나 요즘 관심사를 편하게 말씀해 주세요.'
        if any(w in compact for w in ('고마','감사')):answer='도움이 되어 기뻐요. 또 궁금한 게 있으면 말씀해 주세요.'
        elif request['conditions'].get('region'):answer=location_label(state['location'])+'에서 찾는 걸 기억할게요. 어떤 활동이 궁금하세요?'
        return reply(state,safe,answer,'chat'),safe
    if route in {'explore','home','howto'}:
        if any(w in compact for w in ('다른취미','다른운동','다른활동')):
            state['declined_idea_ids']=list(set(state.get('declined_idea_ids',[]))|{i['id'] for i in old.get('ideas',[])})
            for k in ('activity_type','category','tags','beginner','purpose'):
                if k not in request['update_fields']:state['conditions'].pop(k,None)
        return ideas_reply(state,safe,route,plan),safe
    if route=='followup':
        if any(w in compact for w in ('비싸','돈많이안','저렴')):
            result=reply(state,safe,'비용을 줄여서 찾아볼게요. 무료 활동이 좋으세요, 생각하신 금액이 있으세요?','search','life_budget')
            result['search_requested']=True
            return result,safe
        elif any(w in compact for w in ('멀어','멀어요')):
            state['conditions']['mobility']='가까운 곳'
            result=reply(state,safe,'더 가까운 곳을 원하시는군요. 어느 동네를 기준으로 찾아볼까요?','search','web_dong');result['search_requested']=True
            return result,safe
        else:
            state['declined_ids']=list(set(state.get('declined_ids',[]))|{r['id'] for r in visible_activities(old)})
            if old.get('ideas'):
                state['declined_idea_ids']=list(set(state.get('declined_idea_ids',[]))|{r['id'] for r in old['ideas']})
                return ideas_reply(state,safe,'explore',plan),safe
    state['search_requested']=True;state['conversation_route']='search'
    if not any(state['conditions'].get(k) for k in ('activity_type','category','purpose')):
        return ideas_reply(state,safe,'explore',plan),safe
    loc=state['location']
    if old.get('pending')=='web_dong' and not {'region','neighbourhood'} & set(request['update_fields']):
        result=reply(state,safe,'기준으로 삼을 동네 이름을 알려주세요.','search','web_dong');result['search_requested']=True
        return result,safe
    if not loc.get('city'):
        prompt=question(loc) if loc.get('neighbourhood') or loc.get('district') else '어느 동네에서 찾아볼까요?'
        result=reply(state,safe,prompt,'search','web_location' if loc.get('neighbourhood') or loc.get('district') else 'region');result['search_requested']=True
        return result,safe
    result=public_search(state,settings,activities,as_of=as_of)
    if not result.get('web'):
        from services.continuity import continue_turn
        result=continue_turn(old,result,safe)
        if result.get('recommendation_update'):
            update=result['recommendation_update']
            result['message']='조건을 바꿨어요. '+('앞서 안내한 활동과 순서는 같아요.' if update['same'] else '새 조건에 맞춰 활동을 다시 살펴봤어요.')
            if state['conditions'].get('time_slot'):result['message']+=' 시간은 카드의 공식 일정에서 확인해 주세요.'
    result['history']=(old.get('history',[])+[{'role':'user','content':safe},{'role':'assistant','content':result['message']}])[-20:]
    return result,safe

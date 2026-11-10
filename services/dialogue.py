"""세션에 저장할 순수 대화 상태. 질문·추천·신청 안내는 Python이 결정한다."""

from copy import deepcopy
import re

from services.ai import AIError, empty_extraction, extract_conditions, validate_extraction
from services.alternative_paths import local_rows, district, NEIGHBOURS
from services.recommendation_pipeline import anchor_request, programme_options, prepare_view, adjacent_programmes
from services.personalization import update_modes, profile_conditions
from services.recommendations import recommend
from services.activity_guidance import suggestions, route_intent, supported_region, facility_references, IDEAS


QUESTIONS = {
    "region": "어느 지역에서 찾아볼까요? 지금은 서울 강서구의 공식 자료를 안내해요.",
    "time_slot": "오전, 오후, 저녁 중 언제가 편하세요? 상관없다고 하셔도 돼요.",
    "activity_type": "어떤 활동으로 바꿔볼까요? 운동, 만들기, 공연 등을 말씀해 주세요.",
    "effort_preference": "가볍게 움직이는 운동이 좋으세요, 조금 활발한 운동이 좋으세요?",
    "budget_unit": "말씀하신 예산은 한 번 참여할 때의 금액인가요, 한 달 금액인가요?",
}


def new_state():
    return {"conditions": {}, "any_fields": [], "history": [], "pending": None,
            "results": [], "references": [], "selected_id": None, "mode": "basic",
            "message": "원하는 활동이나 지금 상황을 편하게 말씀해 주세요.", "code": "start", "error": None, "diagnostic": None, "notice": None, "ideas": [], "facilities": [], "flow":"program", "routing_intent":"search_program", "empty_count":0, "alternatives":[], "expansion_consent":None, "expanded":False,"search_scope":{"kind":"local"},"previous_local":None,"adjacent_groups":[],"condition_modes":{},"excluded_types":[]}


def basic_extract(text, state):
    """키가 없을 때 쓰는 제한적 키워드 처리. AI 이해로 표시하지 않는다."""
    request = empty_extraction()
    compact = re.sub(r"\s+", "", text)
    def put(key, value):
        request["conditions"][key] = value
        if key not in request["update_fields"]:
            request["update_fields"].append(key)

    pending = state.get("pending")
    if "시간" in compact and "상관없" in compact:
        request["clear_fields"] = ["time_slot"]
        return request
    if "다른운동" in compact or "다른취미" in compact:
        request["intent"] = "recommend_activity"
        put("category", "체육" if "운동" in compact else "문화·취미")
    if "상관없" in compact or "아무때" in compact or "아무거나" in compact:
        if pending in request["conditions"]:
            request["clear_fields"].append(pending)
        else:
            request["intent"] = "other"
        return request
    if compact in {"네", "예", "응", "좋아요"}:
        request["intent"] = "yes"
        return request
    if compact in {"아니요", "아니", "싫어요"}:
        request["intent"] = "no"
        return request
    if "처음부터" in compact or "새로시작" in compact:
        request["intent"] = "reset"
        return request
    if "다른시간" in compact:
        request["intent"] = "change_time"
        return request
    if "다른활동" in compact:
        request["intent"] = "change_activity"
        return request
    if '인접지역' in compact and any(word in compact for word in ('찾','확인','넓')):
        request['intent']='other'
        return request
    if "신청" in compact or "참여방법" in compact:
        request["intent"] = "apply"
    for index, names in enumerate((("첫번째", "1번"), ("두번째", "2번"), ("세번째", "3번")), 1):
        if any(name in compact for name in names):
            request["selection"] = index
            request["intent"] = "apply"
    region = re.search(r"([가-힣]{1,8}구)", text)
    if region and region.group(1) not in {"친구","도구","농구","축구","탁구","당구","배구","가구","입구","출구"}:
        value = region.group(1)
        put("region", "부산 강서구" if "부산" in text and "강서" in text else value)
    if "서울" in text and not region:
        put("region", "서울")
    if re.search(r"살[아고]|거주", text):
        if "강서구" in text:
            put("residence", "서울 강서구" if "부산" not in text else "부산 강서구")
        elif "서울" in text:
            put("residence", "서울")
    aliases = {
        "걷기": ["걷기", "걷고", "걷는"], "체조": ["체조"], "미술": ["그림", "미술"],
        "수영": ["수영"], "아쿠아로빅": ["아쿠아", "수중운동"],
        "슬로우조깅": ["조깅"], "파크골프": ["파크골프"],
        "가드닝": ["가드닝", "정원", "식물", "만들기"],
        "국악공연": ["국악"], "숲체험": ["숲체험", "숲산책"],
        "인문학": ["인문학"], "시민교육": ["정비사업", "시민교육"],
    }
    for kind, words in aliases.items():
        if any(word in compact for word in words):
            put("activity_type", kind)
    for word, category in (("운동", "체육"), ("체육", "체육"), ("문화", "문화·취미"),
                           ("취미", "문화·취미"), ("평생학습", "평생학습")):
        if word in compact:
            put("category", category)
    times = list(re.finditer("오전|아침|오후|저녁|밤", compact))
    if times:
        value = times[-1].group()
        put("time_slot", {"아침": "오전", "밤": "저녁"}.get(value, value))
    if any(word in compact for word in ('가벼운','가볍게','무리하지','천천히')):
        put('effort_preference','가볍게')
    elif '활발' in compact:
        put('effort_preference','활발하게')
    elif compact in {'보통','보통으로요','보통이요'}:put('effort_preference','보통')
    if "처음" in compact or "초보" in compact:
        put("beginner", True)
    if "초보아니" in compact:
        put("beginner", False)
    if "운동" in compact:put("purpose","운동")
    for word, purpose in (("배우", "배우기"), ("배워", "배우기"), ("관람", "관람"),
                          ("쉬고", "휴식"), ("친구", "교류")):
        if word in compact:
            put("purpose", purpose)
    if '보고' in compact and any(word in compact for word in ('공연','국악','전시')):
        put('purpose','관람')
    age = re.search(r"(\d{1,3})\s*(?:세|살)", text)
    if age:
        put("age", int(age.group(1)))
    for word, gender in (("남성", "남성"), ("남자", "남성"), ("여성", "여성"), ("여자", "여성")):
        if word in text:
            put("gender", gender)
    money = re.search(r"(\d+)\s*(만)?\s*원", text.replace(",", ""))
    if money:
        put("budget_amount", int(money.group(1)) * (10000 if money.group(2) else 1))
    if "무료" in text:
        put("budget_amount", 0)
    if "한달" in compact or "월" == compact:
        put("budget_unit", "월")
    elif "한번" in compact or "회당" in compact:
        put("budget_unit", "회당")
    for words, value in ((('휠체어','이동이어려','멀리못','이동적게'),'이동 적게'),
                         (('가까운곳','집근처'),'가까운 곳'),(('대중교통','버스','지하철'),'대중교통'),(('걸어서','도보'),'도보')):
        if any(word in compact for word in words):put('mobility',value)
    interest_words={'그림':'그림','만들기':'만들기','식물':'식물','산책':'산책','야외':'야외','실내':'실내','공연':'공연'}
    tags=[value for word,value in interest_words.items() if word in compact]
    if tags:put('tags',tags[:5])
    request['intent']=route_intent(text,request,state)
    return validate_extraction(request)


def _reply(state, message, code, pending=None):
    state.update(message=message, code=code, pending=pending)
    state["history"].append({"role": "assistant", "content": message})
    state["history"] = state["history"][-20:]
    return state


def _ideas(state, *, different=False):
    old=[x['id'] for x in state.get('ideas',[])] if different else []
    if different:
        prior_types={option['activity_type'] for option in state.get('alternatives',[])}
        old.extend(idea['id'] for idea in IDEAS if idea['activity_type'] in prior_types)
    state.update(search_scope={'kind':'local'},adjacent_groups=[],alternatives=[],expanded=False,ideas=suggestions(profile_conditions(state),previous=old),facilities=[],results=[],references=[],selected_id=None,flow='ideas')
    notes=[]
    if state['conditions'].get('effort_preference'):notes.append('원하신 강도는 기억하지만 실제 운동 강도는 프로그램에서 확인해야 해요.')
    if different and state['ideas'] and all(x['id'] in old for x in state['ideas']):notes.append('이 조건에서는 다른 제안이 아직 적어요. 다른 활동 찾기로 종류를 넓힐 수 있어요.')
    if state['conditions'].get('time_slot'):notes.append(state['conditions']['time_slot']+' 선호를 기억했어요. 운영시간이 확정된 제안은 아니에요.')
    if state['conditions'].get('budget_amount') is not None:notes.append(f"예산 {state['conditions']['budget_amount']:,}원을 기억했어요. 실제 참가비는 프로그램에서 따로 확인해요.")
    if state['conditions'].get('age') is not None:notes.append(f"말씀하신 {state['conditions']['age']}세는 기억하지만 건강 상태나 운동 능력을 단정하지 않아요.")
    if state['conditions'].get('mobility'):notes.append(state['conditions']['mobility']+' 선호를 기억했어요. 실제 거리·교통 편의는 확인이 필요해요.')
    return _reply(state,'일반적인 활동 아이디어예요. 실제 모집 프로그램은 아니에요. '+ ' '.join(notes)+' 관심 있는 활동을 하나 골라볼까요?', 'ideas','activity_type')


def _search(state, activities, as_of):
    state.update(flow='program',ideas=[],facilities=[],alternatives=[],expanded=False,search_scope={'kind':'local'},adjacent_groups=[])
    if state['conditions'].get('region') and not supported_region(state['conditions']['region']) and not local_rows(activities,state['conditions']['region']):
        state.update(results=[],references=[],selected_id=None,ideas=suggestions(profile_conditions(state)))
        return _reply(state,'현재 확인된 공식 자료는 서울 강서구만 있어요. 요청하신 지역을 실시간 검색한 것은 아니에요. 일반 활동을 고르거나 서울 강서구 자료로 바꿔볼까요?', 'unsupported_region')
    if district(state['conditions'].get('region')):
        state['conditions']['region']=district(state['conditions']['region'])
    outcome = recommend(local_rows(activities,state["conditions"].get("region")) if district(state["conditions"].get("region")) else activities, profile_conditions(state), as_of=as_of)
    state.update(results=outcome["results"], references=outcome["references"], selected_id=None, code=outcome["code"])
    if state['conditions'].get('mobility'):
        for row in state['results']+state['references']:
            row.setdefault('condition_notes',[]).append('말씀하신 이동 편의에 맞는 거리·교통·접근성은 확인이 필요해요.')
    message=outcome['message']
    if not state['results']:
        state['empty_count']=state.get('empty_count',0)+1
        state['ideas']=suggestions(profile_conditions(state),previous=[x['id'] for x in IDEAS if x['activity_type']==state['conditions'].get('activity_type')])
        kind=state['conditions'].get('activity_type') or '요청하신 활동'
        message=f"{kind}에 대해 확인한 결과예요. "+message
        message+=(' 아래는 실제 강좌와 구분한 다른 활동 아이디어예요. 골라서 이어갈 수 있어요.' if state['empty_count']==1
                  else ' 같은 조건에서 새로 확인한 프로그램은 없어요. 다른 활동을 고르거나 시간 조건을 풀어볼 수 있어요.')
        state['alternatives']=programme_options(activities,profile_conditions(state),as_of=as_of)
        state=prepare_view(state,activities,as_of=as_of)
        if state['alternatives']:
            message=(f"{kind}에 정확히 맞는 신청 가능한 강좌는 확인하지 못했어요." if state['empty_count']==1
                     else '같은 조건에서 새 프로그램은 확인되지 않았어요. 아래 대안을 고르거나 시간 조건을 풀어볼 수 있어요.')
        if state.get('expansion_consent') != state['conditions'].get('region') and district(state['conditions'].get('region')) in NEIGHBOURS:
            message=message.split(' 다른 활동으로 찾아볼까요?')[0]
            message=message.replace('다른 시간이나 활동으로 찾아볼까요?', '')
            message=message.replace('?', '.')
            message+=' 인접 지역의 저장된 공식 자료까지 확인할까요?'
            return _reply(state,message,outcome['code'],'expand_region')
    else:state['empty_count']=0
    state=prepare_view(state,activities,as_of=as_of)
    return _reply(state, message, outcome["code"])


def choose_alternative(state, activity_type, activities, settings, *, as_of=None):
    allowed={item['activity_type'] for item in state.get('alternatives',[])}
    if activity_type not in allowed:
        raise ValueError('현재 제안한 대안을 골라주세요.')
    state=deepcopy(state)
    for field in ('activity_type','category','tags'):
        state['conditions'].pop(field,None)
    request=empty_extraction('search_program')
    request['conditions']['activity_type']=activity_type
    request['update_fields']=['activity_type']
    return handle_turn(state,activity_type+' 프로그램을 찾아주세요',activities,settings,extraction=request,as_of=as_of)


def choose_idea(state, idea_id, activities, settings, *, as_of=None):
    allowed={x['id']:x for x in state.get('ideas',[])}
    if idea_id not in allowed:raise ValueError('현재 제안한 활동을 선택해 주세요.')
    idea=allowed[idea_id];state=deepcopy(state)
    for key in ('activity_type','category','tags','beginner'):
        state['conditions'].pop(key,None)
        if key in state['any_fields']:state['any_fields'].remove(key)
    request=empty_extraction('search_program')
    request['conditions'].update(activity_type=idea['activity_type'],category=idea['category'])
    request['update_fields']=['activity_type','category']
    return handle_turn(state,idea['name']+' 프로그램을 찾아주세요',activities,settings,extraction=request,as_of=as_of)


def application_guide(state, activities, *, selected_id=None, as_of=None):
    state = deepcopy(state)
    allowed = {row["id"] for row in state["results"]+state["references"]}
    choice = selected_id or state.get("selected_id")
    if choice is None and len(allowed) == 1:
        choice = next(iter(allowed))
    if choice not in allowed:
        return _reply(state, "어떤 활동의 신청 방법을 볼까요? 결과 카드의 ‘이 활동 신청 방법’을 눌러주세요.", "choose", "selection")
    # 이전 결과도 기준 시점·조건을 다시 검사해 마감된 활동을 신청 가능한 것처럼 안내하지 않는다.
    check_conditions=profile_conditions(state)
    if state.get('expanded'):
        selected=next(row for row in state['results']+state['references'] if row['id']==choice)
        check_conditions['region']=selected['region']
        if check_conditions.get('activity_type')!=selected['activity_type']:
            check_conditions['activity_type']=selected['activity_type']
            check_conditions.pop('category',None);check_conditions.pop('tags',None)
    current = recommend([row for row in activities if row["id"] == choice], check_conditions, as_of=as_of)
    if not current["results"]:
        if current['references']:
            from services.application_helper import start_helper
            row=current['references'][0]
            state.update(results=[],references=current['references'],selected_id=choice,
                         application_helper=start_helper(row,state['conditions'],as_of=as_of),helper_focus=True)
            return _reply(state,current['message']+' 다음 모집을 확인하는 안내예요.',current['code'])
        state.update(results=[], selected_id=None)
        state.pop('application_helper',None)
        return _reply(state, current["message"], current["code"])
    row = current["results"][0]
    from services.application_helper import start_helper
    previous_helper=state.get('application_helper')
    state['application_helper']=(previous_helper if previous_helper and previous_helper['program_id']==choice
                                 else start_helper(row,state['conditions'],as_of=as_of))
    state.pop('recommendation_update',None)
    state['helper_focus']=True
    state["selected_id"] = choice
    notes = " ".join(row.get("condition_notes", []))
    return _reply(state, f"{row['name']}의 공식 신청 방법을 확인해 주세요. "
                  f"{row['registration_method'] or '신청 방법은 기관 확인이 필요해요.'} "
                  f"{notes} 공식 페이지에서 자격과 접수 상태를 확인한 뒤 직접 진행해 주세요. "
                  "아직 신청·예약·결제가 완료된 것은 아니에요.", "apply")


def _search_adjacent(state,activities,as_of):
    origin=state['conditions'].get('region')
    previous=state.get('previous_local') if state.get('flow')=='adjacent' else {'region':origin,'conditions':deepcopy(state['conditions']),
              'results':deepcopy(state['results']),'references':deepcopy(state['references']),
              'alternatives':deepcopy(state.get('alternatives',[])),
              'condition_modes':deepcopy(state.get('condition_modes',{})),'excluded_types':list(state.get('excluded_types',[]))}
    outcome=adjacent_programmes(activities,profile_conditions(state),consent=True,as_of=as_of)
    state.update(flow='adjacent',expanded=True,results=outcome['results'],references=outcome['references'],
        selected_id=None,alternatives=[],ideas=[],facilities=[],previous_local=previous,
        search_scope={'kind':'adjacent','origin':origin,'allowed':outcome['districts'],'covered':outcome['covered']},
        adjacent_groups=outcome['groups'])
    if outcome['results'] or outcome['references']:
        return _reply(state,'동의하신 인접 지역의 저장된 공식 자료를 관련성이 높은 순서로 정리했어요. 각 지역과 접수 상태를 확인해 주세요.', 'expanded_found')
    message=('현재 확인된 인접 지역 프로그램 자료가 없습니다.' if not outcome['covered'] else
             '저장된 인접 지역 자료에서 조건에 맞는 프로그램을 확인하지 못했어요.')
    return _reply(state,message+' 실시간 웹 검색은 하지 않았어요. 이전 강서구 활동은 이전 대화에 남아 있어요.', 'expansion_empty')


def _handle_turn(state, text, activities, settings, *, client=None, as_of=None, extraction=None):
    state = deepcopy(state)
    original_helper=state.get('application_helper')
    original_focus=state.get('helper_focus')
    state.update(error=None, diagnostic=None, notice=None,helper_focus=False)
    state.pop("recommendation_update",None)
    state.pop("application_helper",None)
    navigation={'다음단계':'next','이전단계':'previous','다시설명':'repeat'}
    command=re.sub(r'\s+','',text).rstrip('.!?')
    if original_focus and original_helper and command in navigation:
        from services.application_helper import move_helper
        # Only advance local instructions, never an external application.
        state['application_helper']=deepcopy(original_helper)
        state=move_helper(state,activities,navigation[command],as_of=as_of)
        state['history'][-2]['content']=text
        return state
    previous_flow=state.get("flow","program")
    if state.get('pending') == 'expand_region' and re.sub(r'\s+', '', text).rstrip('.!?') in {'네','예','좋아요','인접지역도확인','아니요','아니','강서구만볼게요','이지역만볼게요'}:
        agree=re.sub(r'\s+', '', text).rstrip('.!?') in {'네','예','좋아요','인접지역도확인'}
        state['history'].append({'role':'user','content':text})
        state['expansion_consent']=state['conditions'].get('region')
        if not agree:
            return _reply(state,'지역을 넓히지 않을게요. 같은 지역의 대안이나 일반 활동을 골라볼까요?', 'expansion_declined')
        return _search_adjacent(state,activities,as_of)
    if not text.strip():
        state["error"] = "질문을 먼저 적어주세요"
        return state
    if len(text) > 1500:
        state["error"] = "질문은 1,500자 이내로 적어주세요."
        return state
    try:
        # 짧은 응답의 의미는 같은 pending/대화 문맥을 사용한다.
        if extraction is not None:
            request = validate_extraction(extraction)
            state["mode"] = "basic"
        elif settings.gemini_api_key:
            request = extract_conditions(text, state, activities, settings, client=client)
            state["mode"] = "gemini"
        else:
            request = basic_extract(text, state)
            state["mode"] = "basic"
            state["diagnostic"] = {"code": "key_missing"}
    except AIError as error:
        state["mode"] = "fallback"
        state["diagnostic"] = {"code": error.code}
        state["notice"] = "Gemini 연결을 이용하지 못해 기본 규칙으로 안내하고 있어요."
        try:
            request = basic_extract(text, state)
        except AIError:
            request = empty_extraction("other")
        if (request["intent"] == "search" and not request["update_fields"]
                and not request["clear_fields"] and "같은조건" not in text.replace(" ", "")):
            request["intent"] = "other"
        if request["intent"] == "other":
            state.update(results=[], references=[])

    request=anchor_request(text,request)
    # 'nearby' is not a license for the model to invent a location.
    if ('근처' in text and not state['conditions'].get('region') and 'region' in request['update_fields']
            and not re.search(r'[가-힣]+(?:구|동)(?:에서|근처|에|요|\s|$)',text)):
        request=deepcopy(request);request['update_fields'].remove('region');request['conditions']['region']=None
    state["history"].append({"role": "user", "content": text})
    intent = route_intent(text,request,state)
    state['routing_intent']=intent
    # Never turn the word 'elderly' into a numeric age.
    if 'age' in request['update_fields'] and not re.search(r'\d{1,3}\s*(?:세|살)',text):
        request=deepcopy(request);request['update_fields'].remove('age');request['conditions']['age']=None
    if intent == "reset":
        return new_state()
    update_modes(state,text,request)
    if '인접지역' in text.replace(' ','') and any(word in text for word in ('찾','확인','넓')) and state.get('flow')!='adjacent':
        return _reply(state,'인접 지역의 저장된 공식 자료까지 확인할까요? 동의하셔야 범위를 넓혀요.', 'question','expand_region')
    for key in request["clear_fields"]:
        state["conditions"].pop(key, None)
        if key not in state["any_fields"]:
            state["any_fields"].append(key)
    for key in request["update_fields"]:
        value = request["conditions"][key]
        if key == "region" and "강서구" in value and "부산" not in value:
            value = "강서구"
        state["conditions"][key] = value
        if key in state["any_fields"]:
            state["any_fields"].remove(key)
    # 구체적 활동을 바꾸면 예전 분류/관심 제한이 새 종류와 충돌하지 않게 한다.
    if "activity_type" in request["update_fields"]:
        for key in ("category", "tags"):
            if key not in request["update_fields"]:
                state["conditions"].pop(key, None)
    if "category" in request["update_fields"] and "activity_type" not in request["update_fields"]:
        state["conditions"].pop("activity_type", None)
        state["conditions"].pop("tags", None)
    if intent=='change_condition':
        intent='recommend_activity' if previous_flow=='ideas' else 'find_facility' if previous_flow=='facility' else 'search_program'
    if 'activity_type' in request['update_fields'] and '말고' not in text:
        state['excluded_types']=[kind for kind in state.get('excluded_types',[]) if kind!=state['conditions'].get('activity_type')]
    if '말고' in text:
        from services.recommendation_pipeline import explicit_activity
        rejected=explicit_activity(text.split('말고',1)[0])
        if rejected:state.setdefault('excluded_types',[]).append(rejected)
    different=bool(re.search(r'다른\s*(운동|활동|취미)',text))
    if different and intent=='recommend_activity':
        for key in ('activity_type','tags','beginner'):
            state['conditions'].pop(key,None)
    if intent == "change_activity":
        for key in ("activity_type", "category", "tags", "beginner"):
            state["conditions"].pop(key, None)
        state.update(search_scope={'kind':'local'},adjacent_groups=[],alternatives=[],expanded=False,results=[], references=[], selected_id=None,facilities=[],ideas=suggestions(profile_conditions(state),previous=[x["id"] for x in state.get("ideas",[])]),flow="ideas")
        return _reply(state, QUESTIONS["activity_type"], "question", "activity_type")
    if intent == "change_time":
        return _reply(state, QUESTIONS["time_slot"], "question", "time_slot")
    if request["selection"]:
        index = request["selection"] - 1
        if index < len(state["results"]):
            state["selected_id"] = state["results"][index]["id"]
        else:
            return _reply(state, "화면에 나온 활동 번호를 다시 골라주세요.", "choose", "selection")
    if intent == 'recommend_activity':
        if not different and '아이디어' not in text and state['conditions'].get('category')=='체육' and not (previous_flow=='ideas' and state.get('ideas')):
            if state['conditions'].get('region'):
                return _search(state,activities,as_of)
            if 'region' not in state['any_fields']:
                state.update(flow='ideas',ideas=[],alternatives=[],results=[],references=[])
                if not state['conditions'].get('effort_preference') and 'effort_preference' not in state['any_fields'] and not state['conditions'].get('activity_type'):
                    return _reply(state,QUESTIONS['effort_preference'],'question','effort_preference')
                return _reply(state,QUESTIONS['region'],'question','region')
        return _ideas(state,different=different)
    if intent == 'find_facility':
        state.update(search_scope={'kind':'local'},adjacent_groups=[],alternatives=[],expanded=False,flow='facility',ideas=[],results=[],references=[],selected_id=None)
        if not state['conditions'].get('region'):
            state['facilities']=[]
            if 'region' in state['any_fields']:
                state['ideas']=suggestions(profile_conditions(state))
                return _reply(state,'지역은 상관없다고 하셨군요. 현재 공식 자료는 서울 강서구만 있어요. 강서구 자료로 찾거나 일반 활동을 골라볼까요?', 'unsupported_region')
            return _reply(state,'근처를 알려면 지역이 필요해요. 어느 구나 동에서 찾아볼까요? 현재 공식 자료는 서울 강서구만 있어요.', 'question','region')
        if not supported_region(state['conditions']['region']):
            state.update(facilities=[],ideas=suggestions(profile_conditions(state)))
            return _reply(state,'요청 지역의 시설 자료는 아직 없어요. 실시간 지도 검색은 하지 않아요. 서울 강서구 자료로 바꾸거나 일반 활동을 골라볼까요?', 'unsupported_region')
        state['facilities']=facility_references(activities,state['conditions'],as_of=as_of)
        if state['facilities']:
            return _reply(state,'공식 프로그램 자료에 나온 관련 시설이에요. 현재 위치나 거리순으로 검색한 결과는 아니며, 운영·요금·강좌는 기관 확인이 필요해요.', 'facilities')
        state['ideas']=suggestions(profile_conditions(state))
        return _reply(state,'확인된 자료에서 해당 시설을 찾지 못했어요. 시설이 없다는 뜻은 아니에요. 다른 활동을 고르거나 지역 조건을 바꿔볼까요?', 'facility_no_match')
    if intent == "apply" and not state['results'] and not state['references'] and (state.get('ideas') or state.get('facilities')):
        if not state.get('ideas'):state['ideas']=suggestions(profile_conditions(state))
        return _reply(state,'아직 신청 가능한 실제 프로그램을 확인하지 못했어요. 일반 활동 제안이나 시설 정보만으로 신청할 수는 없어요. 관심 활동을 골라 프로그램부터 확인할까요?', 'choose','activity_type')
    if intent == "apply" or (intent == "yes" and state["results"] and state["pending"] is None):
        if original_helper and original_helper['program_id']==state.get('selected_id'):
            state['application_helper']=deepcopy(original_helper)
        return application_guide(state, activities, as_of=as_of)
    if intent in {"yes", "no"}:
        return _reply(state, "신청은 자동으로 진행되지 않아요. 원하는 조건을 말씀하거나 아래 버튼을 골라주세요.", "clarify", state["pending"])
    if intent == "other":
        return _reply(state, "어떤 활동을 찾고 싶으세요? 운동, 만들기, 공연처럼 말씀해 주세요.", "clarify")
    if previous_flow=='adjacent' and 'region' not in request['update_fields'] and intent in {'search','search_program','change_condition'}:
        return _search_adjacent(state,activities,as_of)
    state.update(alternatives=[],ideas=[],facilities=[],flow="program")
    conditions = state["conditions"]
    if not conditions.get("region") and "region" not in state["any_fields"]:
        state.update(results=[], references=[])
        return _reply(state, QUESTIONS["region"], "question", "region")
    if (conditions.get("budget_amount", 0) > 0 and not conditions.get("budget_unit")
            and "budget_unit" not in state["any_fields"]):
        return _reply(state, QUESTIONS["budget_unit"], "question", "budget_unit")
    return _search(state, activities, as_of)


def handle_turn(state, text, activities, settings, *, client=None, as_of=None, extraction=None):
    from services.continuity import continue_turn
    updated=_handle_turn(state,text,activities,settings,client=client,as_of=as_of,extraction=extraction)
    return continue_turn(state,updated,text)


def manual_search(state, activities, *, category=None, time_slot=None, as_of=None):
    state = deepcopy(state)
    state.update(conditions={"region": "서울 강서구"}, any_fields=[], history=[],
                 selected_id=None,condition_modes={},excluded_types=[],recommendation_update=None,
                 pending=None, error=None, alternatives=[],expansion_consent=None,expanded=False,mode="manual", diagnostic=None, notice=None, ideas=[],facilities=[],flow="program")
    state.pop('application_helper',None)
    # 지역 문자열은 원본 '서울특별시 강서구'와 부분 일치하도록 저장한다.
    state["conditions"]["region"] = "강서구"
    if category:
        state["conditions"]["category"] = category
    if time_slot:
        state["conditions"]["time_slot"] = time_slot
    return _search(state, activities, as_of)

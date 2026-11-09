"""세션에 저장할 순수 대화 상태. 질문·추천·신청 안내는 Python이 결정한다."""

from copy import deepcopy
import re

from services.ai import AIError, empty_extraction, extract_conditions, validate_extraction
from services.recommendations import recommend


QUESTIONS = {
    "region": "어느 지역에서 찾아볼까요? 지금은 서울 강서구의 공식 자료를 안내해요.",
    "time_slot": "오전, 오후, 저녁 중 언제가 편하세요? 상관없다고 하셔도 돼요.",
    "activity_type": "어떤 활동으로 바꿔볼까요? 운동, 만들기, 공연 등을 말씀해 주세요.",
    "budget_unit": "말씀하신 예산은 한 번 참여할 때의 금액인가요, 한 달 금액인가요?",
}


def new_state():
    return {"conditions": {}, "any_fields": [], "history": [], "pending": None,
            "results": [], "references": [], "selected_id": None, "mode": "basic",
            "message": "원하는 활동이나 지금 상황을 편하게 말씀해 주세요.", "code": "start", "error": None, "diagnostic": None, "notice": None}


def basic_extract(text, state):
    """키가 없을 때 쓰는 제한적 키워드 처리. AI 이해로 표시하지 않는다."""
    request = empty_extraction()
    compact = re.sub(r"\s+", "", text)
    def put(key, value):
        request["conditions"][key] = value
        if key not in request["update_fields"]:
            request["update_fields"].append(key)

    pending = state.get("pending")
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
    if "신청" in compact or "참여방법" in compact:
        request["intent"] = "apply"
    for index, names in enumerate((("첫번째", "1번"), ("두번째", "2번"), ("세번째", "3번")), 1):
        if any(name in compact for name in names):
            request["selection"] = index
            request["intent"] = "apply"
    region = re.search(r"([가-힣]{1,8}구)", text)
    if region:
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
        if word in compact and not request["conditions"]["activity_type"]:
            put("category", category)
    times = list(re.finditer("오전|아침|오후|저녁|밤", compact))
    if times:
        value = times[-1].group()
        put("time_slot", {"아침": "오전", "밤": "저녁"}.get(value, value))
    if "처음" in compact or "초보" in compact:
        put("beginner", True)
    if "초보아니" in compact:
        put("beginner", False)
    for word, purpose in (("배우", "배우기"), ("배워", "배우기"), ("관람", "관람"),
                          ("쉬고", "휴식"), ("친구", "교류")):
        if word in compact:
            put("purpose", purpose)
    age = re.search(r"(\d{1,3})\s*세", text)
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
    return validate_extraction(request)


def _reply(state, message, code, pending=None):
    state.update(message=message, code=code, pending=pending)
    state["history"].append({"role": "assistant", "content": message})
    state["history"] = state["history"][-20:]
    return state


def _search(state, activities, as_of):
    outcome = recommend(activities, state["conditions"], as_of=as_of)
    state.update(results=outcome["results"], references=outcome["references"], selected_id=None)
    return _reply(state, outcome["message"], outcome["code"])


def application_guide(state, activities, *, selected_id=None, as_of=None):
    state = deepcopy(state)
    allowed = {row["id"] for row in state["results"]}
    choice = selected_id or state.get("selected_id")
    if choice is None and len(allowed) == 1:
        choice = next(iter(allowed))
    if choice not in allowed:
        return _reply(state, "어떤 활동의 신청 방법을 볼까요? 결과 카드의 ‘이 활동 신청 방법’을 눌러주세요.", "choose", "selection")
    # 이전 결과도 기준 시점·조건을 다시 검사해 마감된 활동을 신청 가능한 것처럼 안내하지 않는다.
    current = recommend([row for row in activities if row["id"] == choice], state["conditions"], as_of=as_of)
    if not current["results"]:
        state.update(results=[], selected_id=None)
        return _reply(state, current["message"], current["code"])
    row = current["results"][0]
    state["selected_id"] = choice
    notes = " ".join(row.get("condition_notes", []))
    return _reply(state, f"{row['name']}의 공식 신청 방법을 확인해 주세요. "
                  f"{row['registration_method'] or '신청 방법은 기관 확인이 필요해요.'} "
                  f"{notes} 공식 페이지에서 자격과 접수 상태를 확인한 뒤 직접 진행해 주세요. "
                  "아직 신청·예약·결제가 완료된 것은 아니에요.", "apply")


def handle_turn(state, text, activities, settings, *, client=None, as_of=None, extraction=None):
    state = deepcopy(state)
    state.update(error=None, diagnostic=None, notice=None)
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
        elif settings.api_key:
            request = extract_conditions(text, state, activities, settings, client=client)
            state["mode"] = "openai"
        else:
            request = basic_extract(text, state)
            state["mode"] = "basic"
            state["diagnostic"] = {"code": "key_missing"}
    except AIError as error:
        state["mode"] = "fallback"
        state["diagnostic"] = {"code": error.code}
        state["notice"] = "AI 연결을 이용하지 못해 공식 자료를 기본 키워드로 찾아봤어요. 지역·활동·시간 등 일부 조건만 이해하므로 참여 자격은 기관에 확인해 주세요."
        try:
            request = basic_extract(text, state)
        except AIError:
            request = empty_extraction("other")
        if (request["intent"] == "search" and not request["update_fields"]
                and not request["clear_fields"] and "같은조건" not in text.replace(" ", "")):
            request["intent"] = "other"
        if request["intent"] == "other":
            state.update(results=[], references=[])

    state["history"].append({"role": "user", "content": text})
    intent = request["intent"]
    if intent == "reset":
        return new_state()
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
    if intent == "change_activity":
        for key in ("activity_type", "category", "tags", "purpose", "beginner"):
            state["conditions"].pop(key, None)
        state.update(results=[], references=[], selected_id=None)
        return _reply(state, QUESTIONS["activity_type"], "question", "activity_type")
    if intent == "change_time":
        return _reply(state, QUESTIONS["time_slot"], "question", "time_slot")
    if request["selection"]:
        index = request["selection"] - 1
        if index < len(state["results"]):
            state["selected_id"] = state["results"][index]["id"]
        else:
            return _reply(state, "화면에 나온 활동 번호를 다시 골라주세요.", "choose", "selection")
    if intent == "apply" or (intent == "yes" and state["results"] and state["pending"] is None):
        return application_guide(state, activities, as_of=as_of)
    if intent in {"yes", "no"}:
        return _reply(state, "신청은 자동으로 진행되지 않아요. 원하는 조건을 말씀하거나 아래 버튼을 골라주세요.", "clarify", state["pending"])
    if intent == "other":
        return _reply(state, "어떤 활동을 찾고 싶으세요? 운동, 만들기, 공연처럼 말씀해 주세요.", "clarify")
    conditions = state["conditions"]
    if not conditions.get("region") and "region" not in state["any_fields"]:
        state.update(results=[], references=[])
        return _reply(state, QUESTIONS["region"], "question", "region")
    if (conditions.get("budget_amount", 0) > 0 and not conditions.get("budget_unit")
            and "budget_unit" not in state["any_fields"]):
        return _reply(state, QUESTIONS["budget_unit"], "question", "budget_unit")
    return _search(state, activities, as_of)


def manual_search(state, activities, *, category=None, time_slot=None, as_of=None):
    state = deepcopy(state)
    state.update(conditions={"region": "서울 강서구"}, any_fields=[], history=[],
                 pending=None, error=None, mode="manual", diagnostic=None, notice=None)
    # 지역 문자열은 원본 '서울특별시 강서구'와 부분 일치하도록 저장한다.
    state["conditions"]["region"] = "강서구"
    if category:
        state["conditions"]["category"] = category
    if time_slot:
        state["conditions"]["time_slot"] = time_slot
    return _search(state, activities, as_of)

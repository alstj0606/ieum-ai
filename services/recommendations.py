"""공식 자료만으로 추천 후보·사실 카드·안내문을 만든다."""

from services.activities import availability_status, search_activities
from services.personalization import hard_conditions
from services.date_display import registration_display, display_status, display_date_text


STATUS_LABELS = {
    "open": "접수중 표시 · 회차별 잔여석 확인 필요",
    "walk_in": "현장 선착순 · 행사일과 입장 조건 확인",
    "closed": "접수 마감", "unknown": "접수 여부 확인 필요",
    "upcoming": "접수 시작 전", "ended": "활동 기간 종료",
}
# 기존 JSON의 target/verification_notes에 명시된 자격만 구조화한다.
# 원문·출처는 원본 카드에서 항상 함께 표시한다. 성인=특정 나이로 환산하지 않는다.
RULES = {
    "gangseo-slow-jogging-2026-h2-40plus": {"min_age": 40, "residence": "강서구"},
    "heojun-tolerance-humanities-2026": {"adult": True},
    "heojun-beauty-secret-20261121": {"adult": True},
    "botanic-mini-garden-202611": {"adult": True},
    "gaehwasan-forest-space-202611": {"gender": "여성"},
    "seoul-renewal-academy-gangseo-20261121": {"residence": "서울"},
    "seonam-parkgolf-reservation-2026": {"training_required": True},
}


def eligibility(item, conditions):
    rule = RULES.get(item["id"], {})
    warnings = []
    if rule.get("gender"):
        if conditions.get("gender") and conditions["gender"] != rule["gender"]:
            return False, ["공식 참여 대상과 말씀하신 성별 조건이 달라요."]
        if not conditions.get("gender"):
            warnings.append("여성 대상 프로그램이에요. 참여 자격을 확인해 주세요.")
    if "min_age" in rule:
        if conditions.get("age") is not None and conditions["age"] < rule["min_age"]:
            return False, ["공식 최소 연령 조건과 맞지 않아요."]
        if conditions.get("age") is None:
            warnings.append(f"{rule['min_age']}세 이상 대상인지 확인해 주세요.")
    if rule.get("adult"):
        # 법적 성년 나이를 임의 적용하지 않고 명백한 아동만 제외한다.
        if conditions.get("age") is not None and conditions["age"] < 18:
            return False, ["공식 자료에 성인 대상이라고 안내되어 있어요."]
        warnings.append("성인 대상 프로그램이에요. 기관의 참여 기준을 확인해 주세요.")
    if rule.get("residence"):
        residence = conditions.get("residence")
        if residence and (rule["residence"] not in residence
                          or (rule["residence"] == "강서구" and "부산" in residence)):
            return False, ["공식 거주지 자격과 말씀하신 거주지가 달라요."]
        if not residence:
            warnings.append(f"{rule['residence']} 거주 자격을 확인해 주세요. 찾는 지역과 거주지는 달라요.")
    if conditions.get("beginner"):
        if rule.get("training_required"):
            return False, ["초보 교육이 필요한 시설 이용이며 배우는 강좌가 아니에요."]
        warnings.append("초보 참여 가능 여부는 확인된 자료만으로 확정할 수 없어요.")
    return True, warnings


def _purpose_matches(item, purpose):
    if not purpose or purpose == "교류":
        return True
    if purpose == "운동":
        return item["category"] == "체육"
    if purpose == "배우기":
        return "시설이용" not in item["tags"] and item["activity_type"] not in {"국악공연", "야간관람"}
    if purpose == "관람":
        return bool({"전시", "공연"} & set(item["tags"]))
    return bool({"숲", "식물", "국악"} & set(item["tags"]))


def _budget(item, conditions):
    amount = conditions.get("budget_amount")
    if amount is None:
        return "match"
    fee = item["fee_amount"]
    if fee == 0:
        return "match"
    if fee is None:
        return "unknown"
    if amount == 0 and fee > 0:
        return "over"
    # 서로 다른 과금 단위를 자동 환산하지 않는다.
    if conditions.get("budget_unit") == "회당" and item["fee_unit"] == "1인·1회":
        return "match" if fee <= amount else "over"
    return "unknown"


def recommend(activities, conditions, *, as_of=None):
    conditions=hard_conditions(conditions)
    candidates, archived, uncertain = [], [], []
    reasons = {"qualification": 0, "budget": 0, "insufficient": 0, "closed": 0, "unknown": 0}
    broad = 0
    for item in activities:
        if item['activity_type'] in conditions.get('_excluded_types',[]):continue
        found = search_activities(
            [item], activity_type=conditions.get("activity_type"),
            category=conditions.get("category"), region=conditions.get("region"),
            tags=conditions.get("tags"), include_unavailable=True, as_of=as_of,
        )["activities"]
        if not found or not _purpose_matches(item, conditions.get("purpose")):
            continue
        broad += 1
        row = found[0]
        warnings = []
        eligible, eligibility_notes = eligibility(row, conditions)
        if not eligible:
            reasons["qualification"] += 1
            continue
        warnings.extend(eligibility_notes)
        if conditions.get("purpose") == "교류":
            warnings.append("교류 방식이나 단체 활동 여부는 확인이 필요해요.")
        time_slot = conditions.get("time_slot")
        if time_slot and time_slot not in row["schedule"]["time_slots"]:
            if not row["schedule"]["time_slots"]:
                reasons["insufficient"] += 1
            continue
        budget = _budget(row, conditions)
        if budget == "over":
            reasons["budget"] += 1
            continue
        if budget == "unknown":
            warnings.append("비용 또는 과금 단위가 불명확해 예산에 맞는지 확인이 필요해요.")
            reasons["insufficient"] += 1
        row["condition_notes"] = warnings
        status = row["availability_status"]
        if status in {"closed", "ended"}:
            reasons["closed"] += 1
            archived.append(row)
        elif status in {"unknown", "upcoming"}:
            reasons["unknown"] += 1
            archived.append(row)
        elif budget == "unknown":
            uncertain.append(row)
        else:
            candidates.append(row)
    if candidates:
        code = "found"
        message = "확인한 공식 자료에서 활동을 찾았어요. 대상 조건과 실제 접수 가능 여부를 먼저 확인해 주세요."
    elif reasons["qualification"] and broad == reasons["qualification"]:
        code = "qualification"
        message = "관련 활동은 있지만 말씀하신 참여 자격이나 초보 학습 조건과 맞지 않아요. 다른 활동으로 찾아볼까요?"
    elif reasons["closed"]:
        code = "closed"
        message = "관련 활동은 확인했지만 접수가 마감됐거나 활동 기간이 지났어요. 다른 시간이나 활동으로 찾아볼까요?"
    elif reasons["unknown"]:
        code = "unknown"
        message = "관련 활동은 있지만 접수 가능 여부가 확인되지 않았거나 아직 접수 전이에요. 공식 안내를 확인해 주세요."
    elif reasons["insufficient"]:
        code = "insufficient"
        message = "관련 활동의 시간이나 비용 자료가 부족해 조건에 맞는지 확인할 수 없어요. 조건을 바꾸거나 기관에 확인해 볼까요?"
    elif reasons["budget"]:
        code = "budget"
        message = "확인한 요금이 말씀하신 예산보다 높아요. 예산이나 활동을 바꿔볼까요?"
    else:
        code = "no_match"
        message = "현재 확인한 강서구 자료에서는 조건에 맞는 신청 가능한 활동을 찾지 못했어요. 다른 활동으로 찾아볼까요? 지역 전체에 활동이 없다는 뜻은 아니에요."
    return {"code": code, "message": message, "results": candidates[:3],
            "references": (uncertain + archived)[:3] if not candidates else [],
            "total": len(candidates), "reasons": reasons}


def known(value):
    return value if value is not None and value != "" else "확인 필요"


def activity_facts(item, *, as_of=None):
    amount=item.get("fee_amount")
    amount=amount if type(amount) is int and amount>=0 else None
    fee = "무료 (기본 참가비 0원)" if amount == 0 else (
        "공식 자료 확인 필요" if amount is None else
        f"{amount:,}원 · {known(item.get('fee_unit'))}"
    )
    period,times,next_date=registration_display(item,as_of=as_of)
    schedule=item.get("schedule")
    schedule=schedule if isinstance(schedule,dict) else {}
    preparations=[note.split(' 준비 안내.')[0] for note in (item.get('verification_notes') or []) if isinstance(note,str) and ' 준비 안내.' in note]
    facts = [
        ("장소", known(item.get("facility_name"))), ("지역", known(item.get("region"))), ("주소", item.get("address") or "공식 자료 확인 필요"),
        ("일정", known(schedule.get("text"))), ("비용", fee),
        ("비용 참고", known(item.get("fee_notes"))), ("대상", item.get("target") or "공식 자료 확인 필요"),
        ("접수 상태", STATUS_LABELS[display_status(item, as_of=as_of)]),
        ("접수 참고", known(item.get("status_notes"))),
        ("접수 기간", period), ("접수 시각", times), ("다음 접수 예정일", next_date),
        ("준비물", " · ".join(preparations) if preparations else "공식 자료 확인 필요"),
        ("신청 방법", item.get("registration_method") or "공식 자료 확인 필요"), ("정보 확인일", item.get("verified_at")),
    ]
    return [(key,display_date_text(value)) for key,value in facts]


def speech_text(message, results, *, as_of=None):
    """아래 원문은 화면에도 그대로 표시한다. 생성형 요약으로 사실을 바꾸지 않는다."""
    chunks = [message]
    if results:
        item = results[0]
        chunks.append(f"안내할 활동은 {item['name']}입니다.")
        chunks.extend(f"{label}. {value}." for label, value in activity_facts(item, as_of=as_of))
        chunks.extend(item.get("condition_notes", []))
        chunks.append("공식 출처와 안내 페이지 링크는 화면에서 확인해 주세요. 이 서비스에서 신청이 완료되지는 않아요.")
    return "\n".join(chunks)

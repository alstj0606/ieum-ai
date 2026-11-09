"""공식 활동 자료 검증·검색. 외부 요청이나 AI 추론 없이 저장된 값만 사용한다."""

from copy import deepcopy
from collections import Counter
from datetime import date, datetime
import json
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "activities.json"
TIME_SLOTS = {"오전", "오후", "저녁"}
REGISTRATION_STATUSES = {"closed", "unknown", "walk_in", "open"}
AVAILABILITY_STATUSES = REGISTRATION_STATUSES | {"upcoming", "ended"}
SEOUL = ZoneInfo("Asia/Seoul")
REQUIRED_FIELDS = {
    "id", "name", "category", "activity_type", "tags", "region",
    "facility_name", "address", "target", "schedule", "fee_amount", "fee_unit",
    "registration_period", "registration_method", "official_url", "source_url",
    "verified_at", "is_demo", "registration_status", "status_notes",
}


def _text(value, label, *, nullable=False):
    if value is None and nullable:
        return
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}: 비어 있지 않은 문자열이 필요합니다")


def _date(value, label):
    _text(value, label)
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return parsed
    except ValueError as exc:
        raise ValueError(f"{label}: YYYY-MM-DD 날짜가 필요합니다") from exc


def _timestamp(value, label):
    _text(value, label)
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.utcoffset() is None:
            raise ValueError
        return parsed
    except ValueError as exc:
        raise ValueError(f"{label}: 시간대가 포함된 ISO 일시가 필요합니다") from exc


def validate_activities(data):
    """형식 오류는 명시적으로 거부한다. 누락 값을 채우거나 타입을 변환하지 않는다."""
    if not isinstance(data, list):
        raise ValueError("활동 데이터의 최상위는 목록이어야 합니다")
    ids = set()
    for index, item in enumerate(data):
        label = f"활동[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{label}: 객체가 필요합니다")
        missing = REQUIRED_FIELDS - item.keys()
        if missing:
            raise ValueError(f"{label}: 필수 항목 누락 {sorted(missing)}")
        for key in ("id", "name", "category", "activity_type", "region", "facility_name",
                    "status_notes"):
            _text(item[key], f"{label}.{key}")
        if item["id"] in ids:
            raise ValueError(f"중복 id: {item['id']}")
        ids.add(item["id"])
        for key in ("address", "target", "fee_unit", "registration_method"):
            _text(item[key], f"{label}.{key}", nullable=True)
        if not isinstance(item["tags"], list):
            raise ValueError(f"{label}.tags: 문자열 목록이 필요합니다")
        for tag in item["tags"]:
            _text(tag, f"{label}.tags")
        amount = item["fee_amount"]
        if amount is not None and (type(amount) is not int or amount < 0):
            raise ValueError(f"{label}.fee_amount: 0 이상의 원화 정수 또는 null이 필요합니다")
        if type(item["is_demo"]) is not bool:
            raise ValueError(f"{label}.is_demo: bool이 필요합니다")
        if (not isinstance(item["registration_status"], str)
                or item["registration_status"] not in REGISTRATION_STATUSES):
            raise ValueError(f"{label}.registration_status: 지원하지 않는 상태입니다")
        _date(item["verified_at"], f"{label}.verified_at")
        for key in ("official_url", "source_url"):
            _text(item[key], f"{label}.{key}", nullable=key == "official_url")
            if item[key] is not None:
                url = urlsplit(item[key])
                if url.scheme not in {"http", "https"} or not url.hostname:
                    raise ValueError(f"{label}.{key}: HTTP(S) URL이 필요합니다")
        schedule = item["schedule"]
        if not isinstance(schedule, dict) or not {
            "text", "starts_on", "ends_on", "time_slots", "notes"
        } <= schedule.keys():
            raise ValueError(f"{label}.schedule: 일정 객체와 필수 항목이 필요합니다")
        _text(schedule["text"], f"{label}.schedule.text", nullable=True)
        _text(schedule["notes"], f"{label}.schedule.notes", nullable=True)
        for key in ("starts_on", "ends_on"):
            if schedule[key] is not None:
                _date(schedule[key], f"{label}.schedule.{key}")
        if (schedule["starts_on"] and schedule["ends_on"]
                and schedule["starts_on"] > schedule["ends_on"]):
            raise ValueError(f"{label}.schedule: 종료일이 시작일보다 빠릅니다")
        slots = schedule["time_slots"]
        if not isinstance(slots, list) or any(
            not isinstance(slot, str) or slot not in TIME_SLOTS for slot in slots
        ):
            raise ValueError(f"{label}.schedule.time_slots: 오전·오후·저녁 목록이 필요합니다")
        period = item["registration_period"]
        if period is not None:
            if not isinstance(period, dict) or not {
                "starts_at", "ends_at", "notes"
            } <= period.keys():
                raise ValueError(f"{label}.registration_period: 접수 기간 객체가 필요합니다")
            _text(period["notes"], f"{label}.registration_period.notes", nullable=True)
            times = {}
            for key in ("starts_at", "ends_at"):
                if period[key] is not None:
                    times[key] = _timestamp(period[key], f"{label}.registration_period.{key}")
            if len(times) == 2 and times["starts_at"] > times["ends_at"]:
                raise ValueError(f"{label}.registration_period: 종료 시각이 시작보다 빠릅니다")
    return data


def load_activities(path=DATA_PATH):
    """UTF-8 JSON 읽기. 경로는 현재 작업 폴더에 영향받지 않는다."""
    with Path(path).open(encoding="utf-8") as stream:
        return validate_activities(json.load(stream))


def _reference(as_of):
    if as_of is None:
        return datetime.now(SEOUL)
    if isinstance(as_of, datetime):
        if as_of.utcoffset() is None:
            raise ValueError("as_of 일시에는 시간대가 필요합니다")
        return as_of.astimezone(SEOUL)
    if type(as_of) is date:
        return as_of
    raise ValueError("as_of는 date 또는 시간대가 포함된 datetime이어야 합니다")


def _availability(item, reference):
    day = reference.date() if isinstance(reference, datetime) else reference
    if day < date.fromisoformat(item["verified_at"]):
        # 오늘 본 접수중 표시로 확인일 이전의 모집 상태를 소급 확정하지 않는다.
        return "unknown"
    end = item["schedule"]["ends_on"]
    if end is not None and date.fromisoformat(end) < day:
        return "ended"
    status = item["registration_status"]
    if status in {"closed", "unknown"}:
        return status
    if end is None:
        return "unknown"
    if status == "walk_in":
        return "walk_in"
    period = item["registration_period"]
    if not period or not period["starts_at"] or not period["ends_at"]:
        return "unknown"
    start = _timestamp(period["starts_at"], "starts_at").astimezone(SEOUL)
    stop = _timestamp(period["ends_at"], "ends_at").astimezone(SEOUL)
    if not isinstance(reference, datetime):
        start, stop = start.date(), stop.date()
    if reference < start:
        return "upcoming"
    if reference > stop:
        return "closed"
    return "open"


def availability_status(activity, *, as_of=None):
    """저장된 모집 상태와 기준 시점으로 파생 상태를 반환한다. 실시간 조회는 아니다."""
    validate_activities([activity])
    return _availability(activity, _reference(as_of))


def summarize_activities(activities=None, *, as_of=None):
    """검색의 3건 제한과 무관하게 전체 자료의 시점별 상태를 집계한다."""
    data = load_activities() if activities is None else validate_activities(activities)
    reference = _reference(as_of)
    official = [item for item in data if not item["is_demo"]]
    counts = Counter(_availability(item, reference) for item in official)
    return {
        "total": len(official),
        **{status: counts[status] for status in sorted(AVAILABILITY_STATUSES)},
        "participation_options": counts["open"] + counts["walk_in"],
    }


def search_activities(activities=None, *, activity_type=None, region=None,
                      time_slot=None, tags=None, include_unavailable=False,
                      as_of=None, limit=3, category=None, statuses=None):
    """조건은 AND, 태그는 모두 일치. 종류/태그는 정확히, 지역은 부분 일치.

    기본값은 마감·미확인·지난 활동·시연 데이터를 제외한다. 이 자료에서
    현재 접수 가능성을 보증하지 않으며, include_unavailable=True는 조사용이다.
    as_of는 date 또는 시간대 있는 datetime. 미지정 시 한국 현재 시각.
    statuses는 파생 상태 목록이며, 지정하면 기본 상태 필터를 대체한다.
    원본 순서로 최대 3건과 제한 전 일치 건수(total_matches)를 반환한다.
    """
    if type(limit) is not int or limit < 1:
        raise ValueError("limit는 양의 정수여야 합니다")
    if type(include_unavailable) is not bool:
        raise ValueError("include_unavailable은 bool이어야 합니다")
    for label, value in (("activity_type", activity_type), ("region", region),
                         ("time_slot", time_slot), ("category", category)):
        _text(value, label, nullable=True)
    if time_slot is not None and time_slot not in TIME_SLOTS:
        raise ValueError("시간대는 오전·오후·저녁 중 선택하세요")
    if tags is None:
        tags = []
    if not isinstance(tags, (list, tuple)):
        raise ValueError("tags는 문자열 목록이어야 합니다")
    for tag in tags:
        _text(tag, "tags")
    if statuses is not None:
        if not isinstance(statuses, (list, tuple)) or not statuses or any(
            not isinstance(status, str) or status not in AVAILABILITY_STATUSES
            for status in statuses
        ):
            raise ValueError("statuses는 지원하는 상태의 비어 있지 않은 목록이어야 합니다")
    reference = _reference(as_of)
    data = load_activities() if activities is None else validate_activities(activities)
    matches = []
    for item in data:
        if item["is_demo"]:
            continue
        availability = _availability(item, reference)
        if statuses is not None:
            if availability not in statuses:
                continue
        elif not include_unavailable and availability not in {"open", "walk_in"}:
            continue
        if category is not None and item["category"] != category.strip():
            continue
        if activity_type is not None and item["activity_type"] != activity_type.strip():
            continue
        if region is not None and region.strip() not in item["region"]:
            continue
        if time_slot is not None and time_slot not in item["schedule"]["time_slots"]:
            continue
        if not set(tags) <= set(item["tags"]):
            continue
        result = deepcopy(item)
        result["availability_status"] = availability
        matches.append(result)
    if not matches:
        message = "조건에 맞는 확인된 활동이 없어요. 다른 활동 종류나 시간대로 찾아보세요."
    elif include_unavailable or any(
        item["availability_status"] not in {"open", "walk_in"} for item in matches
    ):
        message = "조사용 결과입니다. 마감·과거·미확인 자료가 포함될 수 있어요. 접수 상태와 확인일을 살펴보세요."
    else:
        message = "공식 자료에서 찾은 활동이에요. 현재 운영·접수·입장 가능 여부는 공식 페이지에서 다시 확인해 주세요."
    return {"activities": matches[:min(limit, 3)], "total_matches": len(matches), "message": message}

"""Shared card field contract; detect formatter drift without exposing record data."""
import logging
from services.recommendations import activity_facts
from services.date_display import registration_display, display_date_text, UNKNOWN

CARD_FIELDS=(('참가 비용','비용'),('모집 대상','대상'),('지역','지역'),
             ('장소','장소'),('상세 주소','주소'),('운영 시간','일정'),
             ('접수 기간','접수 기간'),('다음 접수 예정일','다음 접수 예정일'),
             ('신청 방법','신청 방법'),('준비물','준비물'))
DETAIL_FIELDS=('정보 확인일','접수 시각','접수 참고','비용 참고')
REQUIRED_KEYS=tuple(dict.fromkeys(['접수 상태']+[key for _,key in CARD_FIELDS]+list(DETAIL_FIELDS)))


def card_facts(row, *, as_of=None):
    raw=dict(activity_facts(row,as_of=as_of) or [])
    missing=[key for key in REQUIRED_KEYS if key not in raw]
    if missing:
        logging.getLogger(__name__).warning('card_contract_missing_fields: %s',','.join(missing))
    facts={key:display_date_text(value) if isinstance(value,str) and value.strip() and value!='확인 필요' else UNKNOWN for key,value in raw.items()}
    for key in REQUIRED_KEYS:
        facts.setdefault(key,UNKNOWN)
    # Never trust a legacy formatter's raw ISO period or inferred next date.
    facts['접수 기간'],facts['접수 시각'],facts['다음 접수 예정일']=registration_display(row,as_of=as_of)
    if facts['접수 상태']==UNKNOWN:
        facts['접수 상태']='접수 여부 확인 필요'
    return facts

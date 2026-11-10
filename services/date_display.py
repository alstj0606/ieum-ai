"""One defensive presentation boundary for official dates; never edit source data."""
from datetime import date, datetime
import re
from services.activities import availability_status, SEOUL

UNKNOWN='공식 자료 확인 필요'
NEXT_UNKNOWN='다음 접수 일정 미정'


def display_status(item, *, as_of=None):
    try:
        return availability_status(item,as_of=as_of)
    except (ValueError,KeyError,TypeError,AttributeError):
        return 'unknown'


def registration_display(item, *, as_of=None):
    period=item.get('registration_period')
    period=period if isinstance(period,dict) else {}
    def parsed(key):
        value=period.get(key)
        try:
            result=datetime.fromisoformat(value)
            return result.astimezone(SEOUL) if result.utcoffset() is not None else None
        except (ValueError,TypeError,AttributeError):
            return None
    start,stop=parsed('starts_at'),parsed('ends_at')
    if start and stop and start>stop:
        return UNKNOWN,UNKNOWN,NEXT_UNKNOWN
    if start and stop:
        dates=start.strftime('%Y.%m.%d')+' ~ '+stop.strftime('%m.%d' if start.year==stop.year else '%Y.%m.%d')
    elif start:
        dates=start.strftime('%Y.%m.%d')+'부터 · 마감일 '+UNKNOWN
    elif stop:
        dates=stop.strftime('%Y.%m.%d')+'까지 · 시작일 '+UNKNOWN
    else:
        dates=UNKNOWN
    times=' / '.join(label+' '+value.strftime('%Y.%m.%d %H:%M') for label,value in (('시작',start),('마감',stop)) if value)
    next_date=start.strftime('%Y.%m.%d') if start and stop and display_status(item,as_of=as_of)=='upcoming' else NEXT_UNKNOWN
    return dates,times or UNKNOWN,next_date


def display_date_text(text):
    """Normalize date tokens in display text/notes, never URLs or source JSON."""
    if not isinstance(text,str):
        return text
    def timestamp(match):
        try:
            value=datetime.fromisoformat(match.group())
            if value.utcoffset() is None:
                return UNKNOWN
            return value.astimezone(SEOUL).strftime('%Y.%m.%d %H:%M')
        except ValueError:
            return UNKNOWN
    text=re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?',timestamp,text)
    def day(match):
        try:return date.fromisoformat(match.group()).strftime('%Y.%m.%d')
        except ValueError:return UNKNOWN
    return re.sub(r'(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)',day,text)

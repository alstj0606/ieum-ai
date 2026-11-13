"""Provider-neutral read model over verified JSON; unknown attributes remain None."""
import re
from services.activities import availability_status,validate_activities

WEEKDAYS=('월','화','수','목','금','토','일')


def known_weekdays(row):
    schedule=row['schedule']
    if schedule.get('weekdays') is not None:return list(schedule['weekdays'])
    text=schedule.get('text') or ''
    # A closure day is not an operating day. Never expand ranges or date lists.
    if re.search(r'[월화수목금토일]요일\s*(?:휴장|휴강|휴무)',text):return None
    days=re.findall(r'([월화수목금토일])요일',text)
    return list(dict.fromkeys(days)) or None


def catalog_entry(row,*,as_of=None):
    validate_activities([row])
    period=row.get('registration_period') or {}
    from services.application_helper import load_guides
    try:guide=load_guides().get(row['id'],{})
    except (OSError,ValueError):guide={}
    contact=guide.get('contact') or {}
    phone=contact.get('phone')
    if not phone:
        phones=re.findall(r'(?<!\d)0\d{1,2}-\d{3,4}-\d{4}(?!\d)',row.get('registration_method') or '')
        phone=phones[0] if len(set(phones))==1 else None
    if phone and not re.fullmatch(r'0\d{1,2}-\d{3,4}-\d{4}',phone):phone=None
    return dict(activity_id=row['id'],activity_name=row['name'],category=row['category'],
        subcategory=row['activity_type'],description=row.get('description'),organization_name=row.get('organization_name') or contact.get('organization'),facility_name=row['facility_name'],
        institution_id=row.get('institution_id'),region=row['region'],address=row['address'],
        target_age_or_eligibility=row['target'],beginner_friendly=row.get('beginner_friendly'),
        physical_intensity=row.get('physical_intensity'),companionship=row.get('companionship'),
        schedule=dict(row['schedule'],weekdays=known_weekdays(row)),price={'amount':row['fee_amount'],'unit':row['fee_unit']},
        recruitment_start=period.get('starts_at'),recruitment_end=period.get('ends_at'),
        application_status=availability_status(row,as_of=as_of),application_method=row['registration_method'],
        application_url=row['official_url'],contact_phone=phone,contact_role=contact.get('role') or 'inquiry',
        contact_source=guide.get('source_url') or row['source_url'],contact_checked_at=guide.get('verified_at') or row['verified_at'],
        source_url=row['source_url'],source_checked_at=row['verified_at'],is_demo=row['is_demo'],
        notes=list(row.get('verification_notes') or []))


def attribute_fit(row,conditions):
    """Compare explicit structured attributes only. Never derive intensity from age/type."""
    notes=[];unknown=False
    if row.get('physical_intensity')=='높음' and (conditions.get('effort_preference')=='가볍게' or conditions.get('movement_caution')):
        return False,['공식 강도가 높음으로 표시되어 요청하신 가벼운 움직임·부담 확인 조건과 달라요.'],False
    requested=conditions.get('weekdays')
    days=known_weekdays(row)
    if requested:
        if days is None:
            unknown=True;notes.append('희망 요일과 운영일이 맞는지는 확인이 필요해요.')
        elif not set(requested)&set(days):return False,['희망 요일과 공식 운영 요일이 달라요.'],False
    companion=conditions.get('companionship')
    if companion and row.get('companionship')!=companion:
        notes.append('혼자 또는 함께 참여하는 방식은 기관에 확인해 주세요.')
    if conditions.get('movement_caution'):
        notes.append('운동 강도와 신체 부담은 확인 필요예요. 안전 여부를 판단한 추천이 아니며 우려가 있으면 의료진과 상담해 주세요.')
        if row['category']=='체육' and row.get('physical_intensity') is None:unknown=True
    return True,notes,unknown

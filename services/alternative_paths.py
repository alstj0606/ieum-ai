"""Curated activity relationships and consent-scoped official-data search.

Relationships describe a reason to compare activities, never medical suitability,
actual intensity, accessibility, or current admission guarantees.
"""
from copy import deepcopy
from services.recommendations import recommend

# Seoul land-border districts. Extend explicitly with geography review, not an LLM guess.
NEIGHBOURS = {'강서구': ('양천구', '마포구'), '양천구': ('강서구', '구로구', '영등포구'),
              '마포구': ('강서구', '은평구', '서대문구', '중구', '용산구')}
RELATIONS = {
    '걷기': [('체조', '몸을 움직이는 활동이라는 목적이 비슷해요. 동작과 강도는 기관에 확인해요.'),
           ('슬로우조깅', '야외에서 움직이는 활동이에요. 걷기보다 부담이 클 수 있어 강도 확인이 필요해요.'),
           ('파크골프', '야외에서 이동하며 즐기는 다른 운동이에요. 장비·입문 교육·이동 편의를 확인해요.')],
    '수영': [('아쿠아로빅', '물속에서 움직인다는 공통점이 있어요. 수영 입문 강좌와는 달라요.'),
           ('체조', '물 밖에서 몸을 움직이는 대안이에요. 실제 동작과 강도는 확인해요.')],
    '아쿠아로빅': [('수영', '물에서 하는 다른 활동이에요. 기술과 강도가 달라 입문 조건을 확인해요.'), ('체조', '몸을 움직이는 다른 방식이에요. 강도는 확인해요.')],
    '체조': [('걷기', '몸을 움직이는 다른 방식이에요. 경로와 쉬는 곳을 직접 확인해요.'), ('아쿠아로빅', '물속 움직임을 비교해 볼 수 있어요. 강도와 이동 편의는 확인해요.')],
    '슬로우조깅': [('걷기', '속도를 스스로 정하는 움직임을 생각해 볼 수 있어요.'), ('파크골프', '야외 운동의 다른 방식이에요. 교육·장비 조건은 달라요.')],
    '미술': [('가드닝', '손으로 만들고 꾸민다는 관심이 이어져요. 재료와 작업 방식은 확인해요.'), ('전시연계체험', '전시를 보고 직접 해보는 체험을 비교해 볼 수 있어요.')],
    '가드닝': [('전시연계체험', '직접 해보는 문화 체험이라는 공통점이 있어요.'), ('미술', '만들고 꾸미는 관심을 다른 재료로 이어갈 수 있어요.')],
    '인문학': [('시민교육', '새로운 내용을 배우는 목적이 이어져요. 주제와 대상은 달라요.')],
}


def district(region):
    value = (region or '').replace('서울특별시', '').replace('서울시', '').replace('서울 ', '').strip()
    return value if value.endswith('구') and ' ' not in value else None


def local_rows(activities, region):
    key = district(region)
    return [row for row in activities if key and district(row['region']) == key and '서울' in row['region']]


# Comparison taxonomy, not verified per-program intensity/accessibility ratings.
ACTIVITY_TRAITS={
    '걷기': {'movement':'보행','purpose':'운동','pace_change':False,'equipment':False},
    '슬로우조깅': {'movement':'보행','purpose':'운동','pace_change':True,'equipment':False},
    '체조': {'movement':'전신 동작','purpose':'운동','pace_change':False,'equipment':False},
    '파크골프': {'movement':'도구 운동','purpose':'운동','pace_change':False,'equipment':True},
    '수영': {'movement':'수중 동작','purpose':'운동','pace_change':False,'equipment':True},
    '아쿠아로빅': {'movement':'수중 동작','purpose':'운동','pace_change':False,'equipment':True},
}
SIMILAR={'걷기':{'슬로우조깅','체조'},'슬로우조깅':{'걷기'},'수영':{'아쿠아로빅'},
         '아쿠아로빅':{'수영','체조'},'체조':{'걷기'},'미술':{'전시연계체험'},'가드닝':{'미술'}}
MATCH_LABELS={0:'직접 일치',1:'유사 활동',2:'다른 대안'}


def alternative_rank(requested, candidate, conditions, *, available=False, order=0):
    """Auditable lexicographic rank, after hard eligibility/time/budget filters.

    Closed status never overrides relevance. No age-based effort assumption.
    """
    tier=0 if requested==candidate else 1 if candidate in SIMILAR.get(requested,set()) else 2
    source=ACTIVITY_TRAITS.get(requested,{})
    target=ACTIVITY_TRAITS.get(candidate,{})
    purpose_miss=int(bool(conditions.get('purpose') and conditions['purpose'] not in {'배우기','교류'} and target.get('purpose')!=conditions['purpose']))
    effort_caution=int(conditions.get('effort_preference')=='가볍게' and target.get('pace_change',False))
    movement_miss=int(not source.get('movement') or source.get('movement')!=target.get('movement'))
    access_caution=int(conditions.get('mobility') in {'이동 적게','가까운 곳'} and target.get('equipment',False))
    return (tier,purpose_miss,effort_caution,movement_miss,access_caution,int(not available),order)


def related_options(activities, conditions, *, as_of=None):
    """Never relax age/beginner/time/budget/mobility or widen region implicitly."""
    options = []
    for order,(kind, reason) in enumerate(RELATIONS.get(conditions.get('activity_type'), [])):
        changed = deepcopy(conditions)
        for field in ('category', 'tags'):
            changed.pop(field, None)
        changed['activity_type'] = kind
        outcome = recommend(local_rows(activities, conditions.get('region')), changed, as_of=as_of)
        rows = outcome['results'] or outcome['references']
        if rows:
            rank=alternative_rank(conditions.get('activity_type'),kind,conditions,available=bool(outcome['results']),order=order)
            if conditions.get('effort_preference')=='가볍게':
                reason+=' 가벼운 활동을 원하셨지만 실제 강도는 공식 자료 확인이 필요해요.'
            options.append({'activity_type':kind,'reason':reason,'rows':rows,
                            'available':bool(outcome['results']),'rank':rank,'match_label':MATCH_LABELS[rank[0]]})
    return sorted(options,key=lambda option:option['rank'])[:3]


def adjacent_search(activities, conditions, *, consent=False, as_of=None):
    """No query outside the requested district without an explicit consent flag."""
    if not consent:
        return {'results': [], 'references': [], 'districts': [], 'covered': []}
    districts = NEIGHBOURS.get(district(conditions.get('region')), ())
    results, references, covered = [], [], []
    for region in districts:
        rows = local_rows(activities, region)
        if not rows:
            continue
        covered.append(region)
        changed = dict(conditions, region=region)
        outcome = recommend(rows, changed, as_of=as_of)
        results.extend(outcome['results']); references.extend(outcome['references'])
    def unique(rows):
        return list({row['id']: row for row in rows}.values())[:3]
    return {'results': unique(results), 'references': unique(references) if not results else [],
            'districts': list(districts), 'covered': covered}

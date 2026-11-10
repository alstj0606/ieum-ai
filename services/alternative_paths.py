"""Curated activity relationships and consent-scoped official-data search.

Relationships describe a reason to compare activities, never medical suitability,
actual intensity, accessibility, or current admission guarantees.
"""

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
    value=(region or '').replace(' ','').strip()
    for prefix in ('서울특별시','서울시','서울'):
        if value.startswith(prefix):
            value=value[len(prefix):];break
    return value if value.endswith('구') else None


def local_rows(activities, region):
    key = district(region)
    return [row for row in activities if key and district(row['region']) == key and '서울' in row['region']]


from services.activity_ranking import ACTIVITY_TRAITS, SIMILAR, MATCH_LABELS, alternative_rank


def related_options(activities, conditions, *, as_of=None):
    from services.recommendation_pipeline import programme_options
    return programme_options(activities,conditions,as_of=as_of)


def adjacent_search(activities, conditions, *, consent=False, as_of=None):
    from services.recommendation_pipeline import adjacent_programmes
    return adjacent_programmes(activities,conditions,consent=consent,as_of=as_of)

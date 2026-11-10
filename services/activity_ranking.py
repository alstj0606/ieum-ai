"""Shared, deterministic relevance ordering used by search and final rendering."""
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



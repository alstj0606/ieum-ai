"""Session-only condition modes; facts and preferences remain distinct."""
from copy import deepcopy
import re


def update_modes(state,text,request):
    modes=state.setdefault('condition_modes',{})
    compact=re.sub(r'\s+','',text)
    for field in request['clear_fields']:modes.pop(field,None)
    for field in ('time_slot','budget_amount'):
        if field not in request['update_fields']:continue
        soft=any(word in compact for word in ('좋아','좋겠','선호','되도록','가능하면'))
        hard=any(word in compact for word in ('반드시','꼭','만가능','만돼','무료로찾','무료만'))
        modes[field]='preferred' if soft and not hard else 'required'


def profile_conditions(state):
    return dict(state['conditions'],_modes=deepcopy(state.get('condition_modes',{})),
                _excluded_types=list(state.get('excluded_types',[])))


def hard_conditions(conditions):
    result=dict(conditions)
    modes=conditions.get('_modes',{})
    if modes.get('time_slot')=='preferred':result.pop('time_slot',None)
    if modes.get('budget_amount')=='preferred':
        result.pop('budget_amount',None);result.pop('budget_unit',None)
    return result


def personal_note(row,conditions,budget_fit):
    """Only describe verified matches; never promise health effects or accessibility."""
    notes=[]
    region=conditions.get('region')
    if region and region.replace(' ','') in row['region'].replace('서울특별시','서울').replace(' ',''):
        notes.append('말씀하신 지역의 자료예요')
    if conditions.get('_modes',{}).get('time_slot')=='preferred':
        slot=conditions.get('time_slot')
        slots=row['schedule']['time_slots']
        if slot in slots:notes.append(slot+' 선호와 시간이 맞아요')
        elif slots:notes.append(slot+'를 선호하셨지만 기록된 시간은 '+'·'.join(slots)+'이에요')
        else:notes.append('선호 시간에 맞는지는 확인이 필요해요')
    if conditions.get('budget_amount') is not None:
        if row['fee_amount']==0:notes.append('기본 참가비는 무료로 확인됐어요')
        elif budget_fit=='over':notes.append('표시된 비용은 선호 예산을 넘어요')
        elif budget_fit=='unknown':notes.append('비용·과금 단위가 선호 예산에 맞는지 확인이 필요해요')
    if conditions.get('effort_preference'):notes.append('원하신 강도에 맞는지는 확인이 필요해요')
    if conditions.get('mobility'):notes.append('거리와 이동 편의는 확인이 필요해요')
    # One extra sentence, not a paragraph of repeated profile values.
    return ', '.join(notes)+'.' if notes else ''

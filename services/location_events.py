"""Typed, validated location events. Never send a picker selection back to NLP."""
from copy import deepcopy
from services.regions import data,selection,districts,label


def validate_location(location):
    p=location.get('province');d=location.get('district');n=location.get('neighbourhood')
    if d not in districts(p):raise ValueError('unknown region parent')
    if location.get('code'):
        checked=selection(p,d,n)
        if checked['code']!=location['code']:raise ValueError('region code mismatch')
        return checked
    if n:
        # This is a user-named locality, not a guessed legal/admin correspondence.
        return dict(location,kind='user_text',code=None)
    return dict(location,kind='district_scope',code=None)


def confirm_location(state,location,activities,settings):
    from services.life_assistant import reply,public_search
    checked=validate_location(location);checked['status']='confirmed'
    result=deepcopy(state);result['location']=checked
    result['conditions']['region']=' '.join(x for x in (checked['city'],checked['district']) if x)
    if checked.get('neighbourhood'):result['conditions']['neighbourhood']=checked['neighbourhood']
    else:result['conditions'].pop('neighbourhood',None)
    for field in ('location_candidates','location_candidate','picker'):result.pop(field,None)
    result['pending']=None
    requested=bool(state.get('search_requested'))
    if requested and any(result['conditions'].get(k) for k in ('activity_type','category','purpose')):
        result=public_search(result,settings,activities)
    else:
        result=reply(result,label(checked)+' 확인','선택한 동네를 기억할게요. 어떤 활동 이야기를 이어갈까요?','explore')
    result['location']=checked
    result['ai_call']={'attempted':False,'status':'not_attempted'};result['gemini_reply_used']=False
    if result.get('pending') in {'region','web_location','web_dong','location_confirmation'}:result['pending']=None
    result['_scroll_after_picker']=True
    return result

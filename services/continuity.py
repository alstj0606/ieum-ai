"""Compare session turns without reclassifying provider intents or generating facts."""
from copy import deepcopy
from services.date_display import display_date_text

FOLLOWUP_FIELDS={'time_slot','budget_amount','budget_unit','effort_preference','mobility','age','gender','residence','beginner','purpose'}
LABELS={'region':'지역','activity_type':'활동','category':'활동 분야','time_slot':'시간','budget_amount':'예산','budget_unit':'예산 단위','effort_preference':'강도 선호','mobility':'이동 조건','age':'나이','gender':'성별','residence':'거주지','beginner':'입문 조건','purpose':'목적','tags':'관심사'}


def recommended_rows(state):
    rows=state.get('results',[])+state.get('references',[])
    rows += [row for option in state.get('alternatives',[]) for row in option['rows']]
    return list({row['id']:row for row in rows}.values())


def time_evidence(rows,slot):
    notes=[]
    for row in rows[:3]:
        slots=(row.get('schedule') or {}).get('time_slots') or []
        if slot in slots:
            text=f"{row['name']}은 공식 자료에 {slot} 회차가 있어요. 실제 이용일·회차의 자격과 빈자리는 확인이 필요해요."
        elif slots:
            text=f"{row['name']}의 기록된 시간대는 {'·'.join(slots)}이며, {slot} 운영은 확인되지 않았어요."
        else:
            text=f"{row['name']}은 {slot} 운영 여부가 확인되지 않았어요."
        notes.append(text)
    return ' '.join(notes)


def continue_turn(previous,current,text):
    """A condition-only followup compares the same factual candidate snapshot."""
    before=previous.get('conditions',{});after=current['conditions']
    changed={key for key in before.keys()|after.keys() if before.get(key)!=after.get(key)}
    changed |= {key for key in previous.get('condition_modes',{}).keys()|current.get('condition_modes',{}).keys()
                if previous.get('condition_modes',{}).get(key)!=current.get('condition_modes',{}).get(key)}
    repeated=set()
    if not changed and not any(word in text for word in ('프로그램','강좌','신청','예약')):
        if after.get('time_slot') and after['time_slot'] in text and any(word in text for word in ('좋아','선호')):repeated.add('time_slot')
        if after.get('budget_amount')==0 and '무료' in text:repeated.add('budget_amount')
    touched=changed|repeated
    old_rows=recommended_rows(previous);new_rows=recommended_rows(current)
    old_selected=previous.get('selected_id')
    ids={row['id'] for row in new_rows}
    if old_selected in ids and current.get('selected_id') is None:
        current['selected_id']=old_selected
    # Keep an active guide only while its programme is still the selected eligible result.
    old_helper=previous.get('application_helper')
    if old_helper and current.get('selected_id')==old_helper['program_id'] and old_selected in ids:
        current.setdefault('application_helper',deepcopy(old_helper))
    if current.get('selected_id')!=old_selected and not current.get('helper_focus'):
        current.pop('application_helper',None)
    if (current.get('helper_focus') or not old_rows or not touched or not touched<=FOLLOWUP_FIELDS or current.get('error')
            or current.get('code') in {'start','apply','choose','clarify','question'} or previous.get('flow')!=current.get('flow')):
        return current
    old_ids=[row['id'] for row in old_rows];new_ids=[row['id'] for row in new_rows]
    def signature(state):
        return ([r['id'] for r in state.get('results',[])], [r['id'] for r in state.get('references',[])],
                [(x['activity_type'],[r['id'] for r in x['rows']]) for x in state.get('alternatives',[])])
    same=signature(previous)==signature(current)
    added=[]
    for key in sorted(touched):
        value=after.get(key)
        if key in repeated:added.append(LABELS[key]+' 조건은 그대로예요')
        elif value is None:added.append(LABELS[key]+' 조건을 풀었어요')
        elif key=='time_slot':added.append(str(value)+(' 선호를 더했어요' if current.get('condition_modes',{}).get(key)=='preferred' else ' 시간을 필수로 적용했어요'))
        elif key=='budget_amount':added.append(('무료' if value==0 else f'{value:,}원')+(' 선호를 더했어요' if current.get('condition_modes',{}).get(key)=='preferred' else ' 예산을 필수로 적용했어요'))
        else:added.append(LABELS.get(key,key)+' 조건을 바꿨어요')
    retained=[]
    for key in ('region','activity_type','age','effort_preference','purpose','time_slot','budget_amount'):
        if key not in changed and key in before:retained.append((f"{before[key]}세" if key=='age' else '무료 예산' if key=='budget_amount' and before[key]==0 else str(before[key])))
    message=('추가 확인 · ' if repeated else '새 조건 · ')+', '.join(added)+'.'
    if retained:message+=' 유지한 조건 · '+' · '.join(dict.fromkeys(retained))+'.'
    if same:
        message+=' 앞서 안내한 활동과 순서는 같아요. 확인된 자료에서 바뀐 조건으로 새롭게 앞설 활동을 찾지 못했어요.'
    else:
        removed=[r['name'] for r in old_rows if r['id'] not in new_ids]
        added_names=[r['name'] for r in new_rows if r['id'] not in old_ids]
        message+=' 새 조건으로 결과를 다시 비교했어요.'
        if removed:message+=' 이전의 '+', '.join(removed)+'은 바뀐 조건에 맞는 결과에서 빠졌어요.'
        if added_names:message+=' 새로 안내하는 자료는 '+', '.join(added_names)+'이에요. 접수 상태를 함께 확인해 주세요.'
        if not removed and not added_names:message+=' 활동의 순서나 신청 가능·참고 자료 구분이 달라졌어요.'
        if not new_rows:message+=' 이 조건에 맞는 공식 자료를 확인하지 못했어요. 활동이 없다는 뜻은 아니에요.'
    if 'time_slot' in touched and after.get('time_slot'):
        message+=' '+time_evidence(new_rows or old_rows,after['time_slot'])
    if current.get('pending')=='expand_region':message+=' 인접 지역의 저장된 자료까지 확인할까요?'
    current['recommendation_update']={'same':same,'changed':sorted(changed),'retained':retained,
        'hide_repeated_cards':same,'previous_ids':old_ids,'current_ids':new_ids}
    current['last_recommendation']={'ids':old_ids,'selected_id':old_selected,'pending':previous.get('pending')}
    current['message']=display_date_text(message)
    if current.get('history') and current['history'][-1]['role']=='assistant':current['history'][-1]['content']=current['message']
    return current

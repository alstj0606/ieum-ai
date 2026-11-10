"""Verified, read-only participation guidance. No external request or submission."""
from copy import deepcopy
import json
from pathlib import Path
from services.activities import availability_status
from services.recommendations import eligibility, _budget
from services.personalization import hard_conditions
from services.date_display import registration_display, display_date_text, UNKNOWN

PATH=Path(__file__).resolve().parents[1]/'data/application_guides.json'


def load_guides(path=PATH):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data,dict):raise ValueError('신청 안내 자료 형식 오류')
    for guide in data.values():
        for key in ('online','phone_application','visit_application'):
            if type(guide.get(key)) is not bool:raise ValueError('신청 방식 근거 누락')
        for step in (guide.get('steps') or [])+(guide.get('closed_steps') or []):
            if any(not isinstance(step.get(k),str) or not step[k].strip() for k in ('title','action','explanation','site_labels','source_url')):
                raise ValueError('단계별 공식 근거 누락')
    return data


def _step(title,action,explanation,source,labels=None):
    return dict(title=title,action=action,explanation=explanation,source_url=source,site_labels=labels)


def helper_view(row,conditions,helper=None,*,as_of=None,guides=None):
    if guides is None:
        try:guides=load_guides()
        except (OSError,ValueError):guides={}
    guide=guides.get(row['id'],{})
    method=row.get('registration_method') or ''
    # No phone/visit assertions are inferred from arbitrary mentions or negated sentences.
    channels={'online':guide.get('online',bool('인터넷' in method or '누리집 회원가입' in method)),
              'phone':guide.get('phone_application',False),'visit':guide.get('visit_application',False)}
    status=availability_status(row,as_of=as_of)
    eligible,notes=eligibility(row,conditions)
    blocked=not eligible or _budget(row,hard_conditions(conditions))=='over'
    source=row['source_url'];closed=status in {'closed','ended'}
    next_date=registration_display(row,as_of=as_of)[2]
    if blocked:
        mode='blocked'
        steps=[_step('참여 조건을 확인해요','기관에 참여 조건을 먼저 확인해 주세요.',' '.join(notes) or '말씀하신 필수 예산과 비용이 달라요. 신청을 권하지 않아요.',source)]
    elif closed:
        mode='closed'
        steps=guide.get('closed_steps') or [
            _step('이번 접수는 마감됐어요','공식 페이지에서 접수 상태를 확인해 주세요.','지금 신청할 수 있다고 확인된 자료가 아니에요. '+next_date+'.',source),
            _step('다음 모집을 확인해요','공식 페이지의 새 모집 안내를 확인해 주세요.','새 공고의 정확한 날짜가 확인되기 전에는 다음 접수 일정 미정이에요. 과거 접수 기간을 다음 일정으로 쓰지 않아요.',source)]
    elif status!='open':
        mode='check'
        action='공식 페이지에서 예정일을 확인해 주세요.' if status=='upcoming' else '공식 페이지에서 현재 참여 방식을 확인해 주세요.'
        steps=[_step('현재 상태부터 확인해요',action,'현장 선착순은 좌석을 보장하지 않으며, 미확인 접수는 신청 가능으로 안내하지 않아요. '+next_date+'.',source)]
    elif guide.get('steps') and channels['online']:
        mode='online';steps=guide['steps']
    else:
        mode='unverified'
        steps=[_step('신청 절차 확인이 필요해요','공식 페이지를 열어 신청 방법을 확인해 주세요.','이 프로그램의 실제 버튼 순서는 아직 검증하지 못했어요. 확인되지 않은 단계를 만들지 않아요. 확인된 문의처가 있으면 아래에서 문의할 수 있어요.',source)]
    previous=helper or {}
    index=previous.get('index',0) if previous.get('program_id')==row['id'] and previous.get('mode')==mode else 0
    if type(index) is not int:index=0
    index=max(0,min(index,len(steps)-1))
    return {'program_id':row['id'],'name':row['name'],'mode':mode,'status':status,'index':index,'total':len(steps),
            'step':deepcopy(steps[index]),'channels':channels,'contact':deepcopy(guide.get('contact')),
            'visit':deepcopy(guide.get('visit')),'verified_at':guide.get('verified_at'),
            'scope':guide.get('verification_scope','프로그램의 구체적 신청 절차는 미확인'),
            'official_url':row['official_url'],'next_date':next_date,'condition_notes':notes,
            'finished_reading':bool(previous.get('finished_reading')) and previous.get('mode')==mode and previous.get('program_id')==row['id']}


def start_helper(row,conditions,*,as_of=None):
    view=helper_view(row,conditions,as_of=as_of)
    return {key:view[key] for key in ('program_id','mode','index')}


def move_helper(state,activities,direction,*,as_of=None):
    state=deepcopy(state);helper=state.get('application_helper')
    row=next((r for r in activities if helper and r['id']==helper['program_id']),None)
    if row is None:return state
    view=helper_view(row,state['conditions'],helper,as_of=as_of)
    index=view['index']
    if helper.get('mode')!=view['mode']:helper.pop('finished_reading',None)
    if direction=='next':index=min(index+1,view['total']-1)
    elif direction=='previous':index=max(0,index-1)
    elif direction=='finish' and index==view['total']-1:helper['finished_reading']=True
    helper.update(index=index,mode=view['mode'])
    state['recommendation_update']=None
    state['code']='closed' if view['mode']=='closed' else 'apply';state['helper_focus']=True;state['selected_id']=row['id'];state['pending']=None
    updated=helper_view(row,state['conditions'],helper,as_of=as_of)
    state['message']=updated['step']['action']
    state['history']=(state.get('history',[])+[{'role':'user','content':{'next':'다음 단계','previous':'이전 단계','repeat':'다시 설명','finish':'안내를 끝까지 확인했어요','resume':'신청 안내 이어보기'}.get(direction,'신청 안내')},{'role':'assistant','content':helper_speech(updated)}])[-20:]
    return state


def helper_speech(view):
    return f"{view['name']}. {view['index']+1}단계, 전체 {view['total']}단계. {view['step']['title']}. {view['step']['action']} {view['step']['explanation']} 실제 신청 완료 여부는 공식 사이트에서 확인해 주세요."

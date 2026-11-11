"""Single-institution guided screen. Legacy chat/search remains a separate service."""
from pathlib import Path
import streamlit as st
from services.institution_dialogue import load_institution,new_institution_state,guide_turn,current_steps,has_credentials,PRIVACY
from services.config import load_settings
from services.voice import transcribe,synthesize,VoiceError
from ui.signup_visual import visual_guide_html
from services.member_diagnostics import record

ROOT=Path(__file__).resolve().parents[1]


def render():
    st.set_page_config(page_title='이음 AI · 성산복지관 신청 도우미',page_icon='💬')
    st.markdown('<style>'+(ROOT/'ui/chat.css').read_text()+'</style>',unsafe_allow_html=True)
    st.markdown('<style>'+(ROOT/'ui/seongsan_light.css').read_text()+'</style>',unsafe_allow_html=True)
    with st.container(key='seongsan_light'):
        _render_content()


def _render_content():
    data=load_institution()
    try:settings=load_settings(dict(st.secrets))
    except Exception:settings=load_settings()
    if 'institution_session' not in st.session_state:st.session_state.institution_session=new_institution_state()
    if 'inst_visual_preference' not in st.session_state:
        st.session_state.inst_visual_preference=bool(st.session_state.get('inst_visual_guide',False))
    def say(text,action=None,source='chat'):
        record(st.session_state,'before_action',action=action,source=source)
        st.session_state.institution_session=guide_turn(st.session_state.institution_session,text,settings,action=action)
        record(st.session_state,'after_action',action=action,source=source)
        st.session_state.inst_audio=None
        st.session_state.inst_voice_error=None
    def legacy():st.session_state.service_mode='gangseo'
    def start_visual():
        st.session_state.inst_visual_preference=True
        # An experiment opt-in says nothing about welfare membership or account status.
        say('회원 유형부터 확인할게요.',action='reset',source='inst_start_visual')
    def remember_visual():
        # Persist outside the widget key, which Streamlit removes when it is hidden.
        st.session_state.inst_visual_preference=st.session_state.inst_visual_guide
    def button(label,key,text=None,action=None,disabled=False):
        return st.button(label,key=key,on_click=say,args=(text or label,action,key),type='primary',use_container_width=True,disabled=disabled)
    st.title('이음 AI')
    st.caption(data['name']+' · 창원 성산구')
    state=st.session_state.institution_session
    if not state['active']:
        record(st.session_state,'render',screen='welcome')
        st.write('안녕하세요. 이음 AI예요. 복지관 프로그램을 찾고 신청하는 과정을 함께 도와드릴게요.')
        button('프로그램 알아보기','inst_programs',action='program_info')
        button('온라인 신청 도와주세요','inst_start',action='repeat')
        button('복지관 회원가입 안내','inst_membership',action='membership_help')
        st.link_button('전화로 문의하기 · 055-714-9178','tel:0557149178',type='primary',use_container_width=True)
        st.caption('기관 문의 전화예요. 전화 신청 가능 여부는 확인하지 못했어요.')
        with st.expander('실험 · 버튼 찾기 예시'):
            st.write('실제 사이트가 아닌 구조도로 버튼 이름을 연습해요. 공식 사이트의 앱 내부 표시는 아직 검증하지 못했어요.')
            st.button('버튼 찾기 예시 시작',key='inst_start_visual',on_click=start_visual,type='primary',use_container_width=True)
    else:
        steps=current_steps(data,state)
        membership_help=len(steps)==1
        signup=state.get('guide_kind')=='signup'
        step=steps[state['index']]
        record(st.session_state,'render',screen=step['step_id'])
        with st.chat_message('assistant'):
            st.markdown(f'<div id="latest-reply-inst-{state["seq"]}"></div>',unsafe_allow_html=True)
            st.subheader(step['title'] if membership_help else f'{state["index"]+1}단계 / {len(steps)}단계 · {step["title"]}')
            with st.container(key='inst_instruction'):
                st.markdown('**지금 할 일 → '+step['instruction']+'**')
            if membership_help:
                st.link_button('기관에 문의 전화하기 · 055-714-9178','tel:0557149178',type='primary',use_container_width=True)
                st.caption('기관 문의 전화예요. 전화 신청 가능 여부는 확인하지 못했어요.')
            if state['membership'] is True and not signup and state['index'] in (1,2):
                button('온라인 아이디가 있어요 · 로그인 안내','inst_has_id',action='member_with_id')
                button('아이디가 없어요 · 온라인 아이디 만들기','inst_no_id',action='member_without_id')
            if signup:
                if st.toggle('버튼 찾기 예시 보기 · 실제 사이트 아님',key='inst_visual_guide',
                             value=st.session_state.inst_visual_preference,on_change=remember_visual):
                    st.html(visual_guide_html(step))
            if state.get('notice'):st.info(state['notice'])
            if state['message'] and state['message'] not in (step['instruction'],step['details'],'다시 짧게 안내할게요. '+step['instruction']):st.write(state['message'])
            if step['button_label']:st.markdown('**공식 메뉴·버튼 이름 · '+step['button_label']+'**')
            st.write(step['details'])
            st.caption('검증 수준 · '+step['verification_level'])
            if not membership_help:st.warning('현재 모집·신청 자격 미확인 · 인증 이후 절차는 미검증이에요.' if signup else '현재 강좌·모집 상태 미확인 · 2025 안내문은 절차 참고용이에요.')
            if signup:st.caption('2026.11.11 iPad Safari · 이용자가 직접 확인한 절차')
            if not membership_help and state['index']==0 and '회원등록' in state['message']:
                st.write('**방문 회원등록 안내**')
                st.write(data['name']+' · '+data['address'])
                st.write('회원등록 준비물·접수 창구·가능 시간은 현재 확인이 필요해요. 방문 전에 전화로 확인해 주세요.')
            if not membership_help and state['index']==0 and state['membership'] is not True:
                button('복지관 기존 회원이에요','inst_member',text='기존 회원이에요',action='member')
                button('복지관 비회원이에요','inst_nonmember',text='비회원이에요',action='nonmember')
                button('회원 여부를 모르겠어요','inst_unknown_member',action='unknown_member')
            if not membership_help:st.link_button('공식 신청 사이트 열기 →',step['official_url'],type='primary',use_container_width=True)
            if not membership_help and not signup and (state['index']==2 or '아이디' in state['message'] or '로그인' in state['message']):
                st.link_button('공식 로그인 화면 열기',data['login_url'],use_container_width=True)
                st.link_button('기존 회원의 아이디 만들기·본인인증 안내 열기',data['account_url'],use_container_width=True)
            if not membership_help:
                st.caption('확인된 화면 이미지가 없어 글로 안내해요. 버튼 위치는 추측하지 않아요.')
                button('다음 단계 →','inst_next',text='다음',action='next',disabled=state['index']==len(steps)-1)
                button('이전 단계','inst_previous',text='이전',action='previous',disabled=state['index']==0)
            button('다시 설명','inst_repeat',action='repeat')
            button('못 찾겠어요','inst_stuck',action='stuck')
            button('회원 유형 다시 선택' if membership_help else '처음으로' if signup else '처음부터 다시','inst_reset',action='reset')
            st.info(PRIVACY+' 이음 AI는 실제 신청 완료를 확인하지 않아요.')
            if not membership_help:
                st.link_button('기관에 문의 전화하기 · 055-714-9178','tel:0557149178',use_container_width=True)
                st.caption('문의 예시: 복지관 회원등록이나 온라인 신청 과정에서 막혔어요. 현재 신청 방법을 알려주시겠어요?')
            if st.button('답변 듣기',key='inst_listen',disabled=not bool(settings.api_key),use_container_width=True):
                try:st.session_state.inst_audio=synthesize((state['message']+' '+step['instruction']+' '+step['details']+' '+PRIVACY),settings)
                except VoiceError as error:st.session_state.inst_voice_error=str(error)
            if st.session_state.get('inst_audio'):
                st.audio(st.session_state.inst_audio,format='audio/mp3')
                if st.button('음성 안내 중지',key='inst_stop_audio'):st.session_state.inst_audio=None;st.rerun()
            with st.expander('공식 출처·확인 범위'):
                st.link_button('이 단계의 공식 근거',step['verification_source'],use_container_width=True)
                if not signup:st.link_button('2025년 절차 참고 안내문',data['guide_url'],use_container_width=True)
                st.caption('자료 확인일 · '+step['verified_at'])
                st.write(data['signup_verification_note'] if signup else data['verification_note'])
                st.write(data['screenshot_usage'])
    with st.expander('기존 기능 · 강서구 활동 검색'):
        st.write('서울 강서구 공식 활동 10건을 찾던 기존 서비스예요. 성산복지관 프로그램과 섞지 않아요.')
        st.button('강서구 기존 서비스 열기',key='open_gangseo',on_click=legacy,use_container_width=True)
    if st.session_state.get('inst_voice_error'):st.warning(st.session_state.inst_voice_error)
    if st.session_state.get('inst_transcript'):
        with st.expander('음성인식 문장 확인·수정'):
            corrected=st.text_area('인식된 문장',value=st.session_state.inst_transcript,key='inst_corrected')
            if st.button('고친 문장으로 안내받기',key='inst_resend'):say(corrected);st.rerun()
    request=st.chat_input('다음, 못 찾겠어요처럼 말씀해 주세요',key='inst_chat',accept_audio=True,max_chars=1500)
    if request:
        if getattr(request,'audio',None) is not None:
            try:
                text=transcribe(request.audio.getvalue(),settings,filename=request.audio.name)
                st.session_state.inst_transcript=None if has_credentials(text) else text
                st.session_state.pop('inst_corrected',None)
                say(text)
            except VoiceError as error:st.session_state.inst_voice_error=str(error)
        else:say(request if isinstance(request,str) else request.text)
        st.rerun()
    st.html('<script>'+(ROOT/'ui/institution_scroll.js').read_text()+'</script>',unsafe_allow_javascript=True)
    st.html('<script>'+(ROOT/'ui/chat.js').read_text()+'</script>',unsafe_allow_javascript=True)

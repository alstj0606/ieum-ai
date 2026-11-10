"""Single-institution guided screen. Legacy chat/search remains a separate service."""
from pathlib import Path
import streamlit as st
from services.institution_dialogue import load_institution,new_institution_state,guide_turn,PRIVACY
from services.config import load_settings
from services.voice import transcribe,synthesize,VoiceError

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
    def say(text,action=None):
        st.session_state.institution_session=guide_turn(st.session_state.institution_session,text,settings,action=action)
        st.session_state.inst_audio=None
        st.session_state.inst_voice_error=None
    def legacy():st.session_state.service_mode='gangseo'
    def button(label,key,text=None,action=None,disabled=False):
        return st.button(label,key=key,on_click=say,args=(text or label,action),type='primary',use_container_width=True,disabled=disabled)
    st.title('이음 AI')
    st.caption(data['name']+' · 창원 성산구')
    state=st.session_state.institution_session
    if not state['active']:
        st.write('안녕하세요. 이음 AI예요. 복지관 프로그램을 찾고 신청하는 과정을 함께 도와드릴게요.')
        button('프로그램 알아보기','inst_programs',action='program_info')
        button('온라인 신청 도와주세요','inst_start',action='repeat')
        button('복지관 회원가입 안내','inst_membership',action='membership_help')
        st.link_button('전화로 문의하기 · 055-714-9178','tel:0557149178',type='primary',use_container_width=True)
        st.caption('기관 문의 전화예요. 전화 신청 가능 여부는 확인하지 못했어요.')
    else:
        step=data['steps'][state['index']]
        with st.chat_message('assistant'):
            st.markdown(f'<div id="latest-reply-inst-{state["seq"]}"></div>',unsafe_allow_html=True)
            st.subheader(f'{state["index"]+1}단계 / {len(data["steps"])}단계 · {step["title"]}')
            if state.get('notice'):st.info(state['notice'])
            if state['message']:st.write(state['message'])
            with st.container(key='inst_instruction'):
                st.markdown('**지금 할 일 → '+step['instruction']+'**')
            if step['button_label']:st.markdown('**공식 메뉴·버튼 이름 · '+step['button_label']+'**')
            st.write(step['details'])
            st.caption('검증 수준 · '+step['verification_level'])
            st.warning('현재 강좌·모집 상태 미확인 · 2025 안내문은 절차 참고용이에요.')
            if state['membership'] is False or (state['index']==0 and '회원등록' in state['message']):
                st.write('**방문 회원등록 안내**')
                st.write(data['name']+' · '+data['address'])
                st.write('회원등록 준비물·접수 창구·가능 시간은 현재 확인이 필요해요. 방문 전에 전화로 확인해 주세요.')
            if state['index']==0:
                button('복지관 기존 회원이에요','inst_member',text='기존 회원이에요',action='member')
                button('복지관 비회원이에요','inst_nonmember',text='비회원이에요',action='nonmember')
            st.link_button('공식 신청 사이트 열기 →',step['official_url'],type='primary',use_container_width=True)
            if state['index']==2 or ('아이디' in state['message'] or '로그인' in state['message']):
                st.link_button('공식 로그인 화면 열기',data['login_url'],use_container_width=True)
                st.link_button('기존 회원의 아이디 만들기·본인인증 안내 열기',data['account_url'],use_container_width=True)
            st.caption('확인된 화면 이미지가 없어 글로 안내해요. 버튼 위치는 추측하지 않아요.')
            button('다음 단계 →','inst_next',text='다음',action='next',disabled=state['index']==len(data['steps'])-1)
            button('이전 단계','inst_previous',text='이전',action='previous',disabled=state['index']==0)
            button('다시 설명','inst_repeat',action='repeat')
            button('못 찾겠어요','inst_stuck',action='stuck')
            button('처음부터 다시','inst_reset',action='reset')
            st.info(PRIVACY+' 이음 AI는 실제 신청 완료를 확인하지 않아요.')
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
                st.link_button('2025년 절차 참고 안내문',data['guide_url'],use_container_width=True)
                st.caption('자료 확인일 · '+step['verified_at'])
                st.write(data['verification_note'])
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
                st.session_state.inst_transcript=text
                st.session_state.pop('inst_corrected',None)
                say(text)
            except VoiceError as error:st.session_state.inst_voice_error=str(error)
        else:say(request if isinstance(request,str) else request.text)
        st.rerun()
    st.html('<script>'+(ROOT/'ui/institution_scroll.js').read_text()+'</script>',unsafe_allow_javascript=True)
    st.html('<script>'+(ROOT/'ui/chat.js').read_text()+'</script>',unsafe_allow_javascript=True)

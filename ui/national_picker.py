"""Touch-only hierarchy: native buttons never summon a text keyboard."""
import streamlit as st
from services.regions import provinces,districts,neighbourhoods,selection,short,label


PICKER_VERSION='touch-confirm-v2'


def close():st.session_state.region_open=False

def open_picker(location=None):
    st.session_state.region_draft={'stage':'province'}
    st.session_state.region_open=True


def choose(level,value):
    draft=st.session_state.region_draft
    if level=='province':draft.update(province=value,district=None,neighbourhood=None,stage='district')
    elif level=='district':draft.update(district=value,neighbourhood=None,stage='neighbourhood')
    elif level=='neighbourhood':draft.update(neighbourhood=value,stage='confirm')
    elif level=='all':draft.update(neighbourhood=None,stage='confirm')


def previous():
    draft=st.session_state.region_draft
    draft['stage']={'district':'province','neighbourhood':'district','confirm':'neighbourhood'}.get(draft['stage'],'province')


def current_selection():
    draft=st.session_state.region_draft;p=draft['province'];d=draft['district'];n=draft.get('neighbourhood')
    return selection(p,d,n) if n else dict(province=p,city=short(p),district=d,neighbourhood=None,code=None,kind='district_scope')


@st.dialog('우리 동네 선택하기',width='small',dismissible=True,on_dismiss=close)
def render(on_complete):
    size=(18,20,22)[st.session_state.get('font_level',0)]
    st.html('<style>.st-key-national_picker_content :is(p,label) {font-size:'+str(size)+'px}.st-key-national_picker_content button {min-height:48px;margin:2px 0;padding:9px 12px}.st-key-national_picker_content .stButton button[kind=secondary] {background:#fff;color:#151515;border:1px solid #b5b5bd}.st-key-national_picker_content .stButton button[kind=secondary]:hover {background:#fff1e7;color:#151515}.st-key-national_picker_content .stButton button[kind=secondary] p {color:#151515}.st-key-national_picker_content .stButton button[kind=primary] p {color:#fff}.st-key-national_picker_content [class*=st-key-region_option_] button {background:#fff;border:1px solid #d4d4da;color:#151515;text-align:left;justify-content:space-between}[role=dialog]:has(.st-key-national_picker_content) {max-height:calc(100vh - 72px);max-height:calc(100dvh - 72px);overflow-y:auto}</style>')
    with st.container(key='national_picker_content'):
        draft=st.session_state.region_draft;stage=draft['stage'];p=draft.get('province');d=draft.get('district')
        titles={'province':'어느 시·도에서 찾아볼까요?','district':'어느 시·군·구인가요?','neighbourhood':'어느 읍·면·동인가요?','confirm':'선택한 동네가 맞나요?'}
        st.write('**'+titles[stage]+'**')
        if p:st.caption(' › '.join(x for x in (p,d) if x))
        if stage=='confirm':
            loc=current_selection();st.write('**'+label(loc)+'**')
            st.write('선택하신 동네가 맞는지 확인해 주세요.')
            if st.button('확인',key='region_confirm',type='primary',use_container_width=True):
                close();on_complete(loc);st.rerun()
        else:
            options=provinces() if stage=='province' else districts(p) if stage=='district' else neighbourhoods(p,d)
            level={'province':'province','district':'district','neighbourhood':'neighbourhood'}[stage]
            # Bounded native scroll container; no editable controls in this path.
            with st.container(height=200,border=False,key='region_touch_list'):
                for i,value in enumerate(options):
                    st.button(value+' →',key='region_option_'+stage+'_'+str(i),on_click=choose,args=(level,value),use_container_width=True)
            if stage=='neighbourhood':st.button('이 시·군·구 전체에서 찾기',key='region_all',on_click=choose,args=('all',None),use_container_width=True)
        left,right=st.columns(2)
        if stage!='province':left.button('이전',key='region_previous',on_click=previous,use_container_width=True)
        if right.button('닫기',key='region_close',on_click=close,use_container_width=True):st.rerun()
        # Free typing is intentionally a separate action, never auto-focused.
        if st.button('동네 이름은 채팅에 적을게요',key='region_type_in_chat',use_container_width=True):
            close();st.rerun()

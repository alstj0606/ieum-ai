"""Native dismissible Streamlit dialog; only a completed explicit choice is applied."""
import streamlit as st
from services.regions import provinces,districts,neighbourhoods,selection,data,label


def close():st.session_state.region_open=False

def open_picker(location=None):
    location=location or {};p=location.get('province');d=location.get('district');n=location.get('neighbourhood')
    if p not in provinces():p=d=n=None
    elif d not in districts(p):d=n=None
    elif n not in neighbourhoods(p,d):n=None
    st.session_state.national_province=p;st.session_state.national_district=d;st.session_state.national_dong=n
    st.session_state.region_applied=(p,d,n);st.session_state.region_open=True


def province_changed():
    st.session_state.national_district=None;st.session_state.national_dong=None

def district_changed():st.session_state.national_dong=None


@st.dialog('지역 선택하기',width='small',dismissible=True,on_dismiss=close)
def render(on_complete):
    size=(18,20,22)[st.session_state.get('font_level',0)]
    st.html('<style>.st-key-national_picker_content {font-size:'+str(size)+'px} .st-key-national_picker_content :is(p,label) {font-size:'+str(size)+'px} .st-key-national_picker_content [data-baseweb=select]>div {min-height:44px;font-size:'+str(size)+'px} body:has(.st-key-national_picker_content) [role=option] {min-height:44px}</style>')
    with st.container(key='national_picker_content'):
        st.caption('행정동 기준 · '+data()['metadata']['snapshot_at']+' 자료. 법정동 이름은 채팅에 직접 적어도 괜찮아요.')
        p=st.selectbox('시·도',provinces(),index=None,key='national_province',placeholder='시·도를 골라주세요',on_change=province_changed)
        d=st.selectbox('시·군·구',districts(p),index=None,key='national_district',placeholder='시·군·구를 골라주세요',on_change=district_changed) if p else None
        n=st.selectbox('읍·면·동',neighbourhoods(p,d),index=None,key='national_dong',placeholder='읍·면·동을 골라주세요') if d else None
        if n and (p,d,n)!=st.session_state.get('region_applied'):
            loc=selection(p,d,n);st.session_state.region_applied=(p,d,n);close();on_complete(loc);st.rerun()
        if p and d:
            st.caption('선택 중 · '+p+' '+d)
            if st.button('이 시·군·구 전체에서 찾기',key='region_all',use_container_width=True):
                from services.regions import short
                close();on_complete(dict(province=p,city=short(p),district=d,neighbourhood=None,code=None,kind='district_scope'));st.rerun()
        if st.button('닫기',key='region_close',on_click=close,use_container_width=True):st.rerun()

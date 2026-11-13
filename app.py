"""활동 관심에서 시작하는 기본 진입점. 기관 안내는 선택한 공식 활동에서만 연다."""
from pathlib import Path
import runpy
import streamlit as st
from services.discovery import institution_for_selection
from services.activities import load_activities

ROOT=Path(__file__).resolve().parent
try:rows=load_activities() if st.session_state.get('service_mode')=='seongsan' else []
except (OSError,ValueError):rows=[]
selected=institution_for_selection(st.session_state.get('dialog',{}),rows)
if st.session_state.get('service_mode')=='seongsan' and selected=='seongsan_senior':
    st.session_state.institution_context=True
    from ui.seongsan_app import render
    render()
else:
    st.session_state.pop('institution_context',None)
    runpy.run_path(str(ROOT/'gangseo_app.py'),init_globals={'DISCOVERY':True},run_name='__main__')

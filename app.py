"""기관 신청 안내가 기본이며, 이전 강서구 서비스는 독립된 화면으로 보존한다."""
from pathlib import Path
import runpy
import streamlit as st

ROOT=Path(__file__).resolve().parent
if st.session_state.get('service_mode','seongsan')=='gangseo':
    runpy.run_path(str(ROOT/'gangseo_app.py'),run_name='__main__')
else:
    from ui.seongsan_app import render
    render()

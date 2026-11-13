"""기존 기관 안내의 독립 실행·회귀 검증 진입점. 기본 서비스는 app.py."""
from pathlib import Path
import runpy
import streamlit as st

ROOT=Path(__file__).resolve().parent
if st.session_state.get('service_mode','seongsan')=='gangseo':
    runpy.run_path(str(ROOT/'gangseo_app.py'),run_name='__main__')
else:
    from ui.seongsan_app import render
    render()

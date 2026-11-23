"""Local-only mock server entrypoint. Never deploy; callbacks also stay mocked."""
from pathlib import Path
import runpy,sys
import streamlit as st
sys.path.insert(0,str(Path(__file__).parent))
from web_fixture import FakeTransport,HTML
from services.config import Settings
from services.ai import AIError
import services.config as config
import services.web_search as web_search
import services.dialogue as dialogue
case=st.query_params.get('case','ok')
mode=case if case in {'quota','empty','page_error','timeout'} else 'ok'
html=HTML.replace('2099','2020') if case=='past' else HTML
# These process-local fixture bindings outlive runpy: Streamlit invokes callbacks
# before rerunning this file. A temporary patch context would leak real requests.
config.load_settings=lambda *args,**kwargs:Settings(search_api_key='local-test-only',gemini_api_key='local-mock-only')
web_search.Transport=lambda:FakeTransport(mode,html)
def unavailable(*args,**kwargs):raise AIError(code='timeout')
dialogue.extract_conditions=unavailable
runpy.run_path(str(Path(__file__).resolve().parents[1]/'app.py'),run_name='__main__')

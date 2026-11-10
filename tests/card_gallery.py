"""Browser-only fixture: show all existing official records, never new programs/API calls."""
from contextlib import nullcontext
from pathlib import Path
import sys
from unittest.mock import patch
import streamlit as st

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from services.activities import load_activities
from services.dialogue import new_state
from services.card_view import activity_facts

if '_gallery_loaded' not in st.session_state:
    turns=[]
    for row in load_activities():
        state=new_state();state.update(references=[row],code='reference')
        turns.append({'user':'공식 자료 카드 검사','state':state,'detail_first':True})
    st.session_state.turns=turns
    st.session_state.turn_seq=len(turns)
    st.session_state._gallery_loaded=True


def legacy_facts(row, **kwargs):
    facts=dict(activity_facts(row,**kwargs))
    facts.pop('다음 접수 예정일',None);facts.pop('준비물',None)
    facts['대상']=None
    period=row.get('registration_period') or {}
    facts['접수 기간']=' ~ '.join(value for value in (period.get('starts_at'),period.get('ends_at')) if value)
    return list(facts.items())

context=patch('services.card_view.activity_facts',side_effect=legacy_facts) if st.query_params.get('legacy')=='1' else nullcontext()
with context:
    exec(compile((ROOT/'gangseo_app.py').read_text(),str(ROOT/'gangseo_app.py'),'exec'),{'__file__':str(ROOT/'gangseo_app.py'),'__name__':'__main__'})

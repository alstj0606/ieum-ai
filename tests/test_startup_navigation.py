"""Regression for institution startup depending on a legacy-only module export.

Subprocesses deliberately start with an empty Python module cache; no live API calls.
"""
import os
from pathlib import Path
import subprocess
import sys
from unittest import TestCase

ROOT=Path(__file__).resolve().parents[1]

class StartupNavigationTest(TestCase):
    def fresh(self,code):
        env=dict(os.environ)
        for key in ('GEMINI_API_KEY','OPENAI_API_KEY'):env.pop(key,None)
        result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,env=env,text=True,capture_output=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr[-4000:])

    def test_navigation_has_no_other_project_imports(self):
        self.fresh("import sys; import services.guide_navigation; assert {n for n in sys.modules if n.startswith('services.')}=={'services.guide_navigation'}")

    def test_legacy_public_export_remains_same_function(self):
        from services.application_helper import advance_step as legacy
        from services.guide_navigation import advance_step
        self.assertIs(legacy,advance_step)

    def test_navigation_boundaries_unchanged(self):
        from services.guide_navigation import advance_step
        for index,total,direction,expected in [(0,6,'previous',0),(0,6,'next',1),(5,6,'next',5),(5,6,'previous',4),(2,6,'repeat',2),(0,1,'next',0)]:
            with self.subTest(index=index,direction=direction):self.assertEqual(advance_step(index,total,direction),expected)

    def test_institution_works_with_legacy_module_missing_export(self):
        # This simulates an old loaded module, not proof about a live Cloud process.
        self.fresh('''
import sys,types
legacy=types.ModuleType('services.application_helper')
sys.modules[legacy.__name__]=legacy
from services.institution_dialogue import new_institution_state,guide_turn
from services.config import Settings
state=guide_turn(new_institution_state(),'기존 회원이에요',Settings())
state=guide_turn(state,'다음',Settings())
assert state['index']==2
assert sys.modules[legacy.__name__] is legacy and not hasattr(legacy,'advance_step')
''')

    def test_fresh_streamlit_script_runner_starts_without_legacy_helper(self):
        self.fresh('''
import importlib.abc,sys
class RejectLegacy(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname=='services.application_helper':
            raise ModuleNotFoundError('legacy helper intentionally unavailable in startup test')
sys.meta_path.insert(0,RejectLegacy())
from streamlit.testing.v1 import AppTest
app=AppTest.from_file('app.py',default_timeout=15).run()
assert not app.exception
app.button(key='inst_start').click().run()
app.button(key='inst_member').click().run()
assert app.session_state['institution_session']['index']==1
app.chat_input(key='inst_chat').set_value('다음').run()
assert app.session_state['institution_session']['index']==2
app.button(key='inst_previous').click().run()
assert app.session_state['institution_session']['index']==1
app.run()
assert not app.exception and 'services.application_helper' not in sys.modules
''')

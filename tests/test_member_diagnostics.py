"""Safe diagnostics, runtime/file distinction, and exact callback-to-render traces."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from services.config import Settings
from services.member_diagnostics import begin,record,report,snapshot,function_matches_file,build_info,TRACE
from ui import seongsan_app

ROOT=Path(__file__).resolve().parents[1]

class MemberDiagnosticsTest(TestCase):
    def test_disabled_does_not_trace_or_change_application_state(self):
        original={'membership':False,'view':'membership_registration','index':0}
        session={'institution_session':deepcopy(original)}
        begin(session,False);record(session,'before_action',source='inst_nonmember',action='nonmember')
        self.assertNotIn(TRACE,session);self.assertEqual(session['institution_session'],original)

    def test_whitelist_omits_raw_values_and_stays_bounded(self):
        canary='private-value-not-for-diagnostics'
        original={'membership':False,'online_account':None,'seq':4,'index':0,'view':'membership_registration',
                  'guide_kind':'application','member_type':'nonmember','active':True,
                  'message':canary,'history':[canary],'api_key':canary,'audio':canary}
        session={'institution_session':deepcopy(original),'arbitrary_secret':canary}
        begin(session,True)
        for _ in range(30):record(session,'before_action',source=canary,action=canary,screen=canary)
        self.assertEqual(len(session[TRACE]),24);self.assertNotIn(canary,json.dumps(session[TRACE]))
        self.assertEqual(session['institution_session'],original)
        self.assertEqual(session[TRACE][-1]['source'],'other')
        begin(session,False);self.assertNotIn(TRACE,session);self.assertEqual(session['institution_session'],original)
        self.assertNotIn(canary,json.dumps(snapshot({'membership':canary,'view':canary,'index':canary})))

    def test_loaded_code_is_compared_to_disk_not_inspect_source(self):
        with TemporaryDirectory() as temp:
            path=Path(temp)/'module.py';old='def current_steps():\n    return "old question"\n'
            path.write_text(old);namespace={};exec(compile(old,str(path),'exec'),namespace)
            loaded=namespace['current_steps'];self.assertTrue(function_matches_file(loaded,path))
            path.write_text('def current_steps():\n    return "new outcome"\n')
            self.assertFalse(function_matches_file(loaded,path))
            self.assertEqual(loaded(),'old question')  # Inspection does not reload or repair it.
            self.assertIsNone(function_matches_file(None,path))
            self.assertIsNone(function_matches_file(loaded,path/'missing'))

    def test_build_report_does_not_infer_missing_commit_or_leak_git_errors(self):
        error='private-git-error'
        with patch('services.member_diagnostics.subprocess.run',return_value=SimpleNamespace(returncode=1,stdout=error,stderr=error)):
            info=build_info(ROOT,seongsan_app)
        self.assertIsNone(info['working_tree_commit']);self.assertIsNone(info['tracked_files_changed'])
        self.assertNotIn(error,json.dumps(info));self.assertTrue(all(info['loaded_functions_match_files'].values()))

    def test_trace_can_distinguish_state_reset_from_rendering_error(self):
        session={'institution_session':{'membership':False,'seq':2,'index':0,'view':'membership_registration'}}
        begin(session,True);record(session,'after_action',source='inst_nonmember',action='nonmember')
        session['institution_session']={'membership':None,'seq':1,'index':0,'view':'guide'}
        begin(session,True)
        self.assertIs(session[TRACE][-2]['state']['membership'],False)
        self.assertIsNone(session[TRACE][-1]['state']['membership'])
        self.assertGreater(session[TRACE][-1]['run'],session[TRACE][-2]['run'])
        # No state repair: evidence stays available exactly as observed.
        self.assertIsNone(session['institution_session']['membership'])

    def test_both_entries_callback_after_state_next_entry_and_render_match(self):
        for entry in ('inst_start','inst_start_visual'):
            with self.subTest(entry=entry),patch('ui.seongsan_app.load_settings',return_value=Settings()):
                app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=15)
                app.query_params['diagnostics']='1';app.run()
                app.button(key=entry).click().run();app.button(key='inst_nonmember').click().run();app.run()
                self.assertFalse(app.exception)
                events=list(app.session_state[TRACE])
                before=next(e for e in events if e['phase']=='before_action' and e.get('source')=='inst_nonmember')
                after=next(e for e in events if e['phase']=='after_action' and e.get('source')=='inst_nonmember')
                rendered=next(e for e in events if e['phase']=='render' and e.get('screen')=='membership_registration')
                self.assertIsNone(before['state']['membership']);self.assertIs(after['state']['membership'],False)
                self.assertGreater(after['state']['seq'],before['state']['seq'])
                self.assertIs(rendered['state']['membership'],False)
                later=[e for e in events if e['event']>after['event'] and e['phase'] in ('entry','render','post_render')]
                self.assertTrue(later);self.assertTrue(all(e['state']['membership'] is False for e in later))
                self.assertEqual(app.subheader[0].value,'비회원 · 방문 회원등록 안내')
                self.assertTrue(any('member-trace-1' in c.value for c in app.code))
                app.query_params.clear();app.run();self.assertNotIn(TRACE,app.session_state)
                self.assertEqual(app.subheader[0].value,'비회원 · 방문 회원등록 안내')

    def test_sensitive_chat_is_not_in_report(self):
        with patch('ui.seongsan_app.load_settings',return_value=Settings()):
            app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=15)
            app.query_params['diagnostics']='1';app.run();app.button(key='inst_start_visual').click().run()
            app.chat_input(key='inst_chat').set_value('비밀번호: private-canary').run()
            payload=report(app.session_state,ROOT,seongsan_app)
            self.assertNotIn('private-canary',json.dumps(payload));self.assertFalse(app.exception)

    def test_simulated_old_renderer_is_detected_without_repair_or_false_cloud_claim(self):
        # Controlled reproduction only; not evidence about the live Cloud process.
        scope={}
        source="def current_steps(data,state):\n    return data['signup_steps'] if state.get('guide_kind')=='signup' else data['steps']\n"
        exec(compile(source,str(ROOT/'services/institution_dialogue.py'),'exec'),scope)
        with patch('ui.seongsan_app.current_steps',scope['current_steps']),patch('ui.seongsan_app.load_settings',return_value=Settings()):
            app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=15)
            app.query_params['diagnostics']='1';app.run();app.button(key='inst_start_visual').click().run()
            app.button(key='inst_nonmember').click().run()
            payload=report(app.session_state,ROOT,seongsan_app)
            self.assertFalse(payload['build']['loaded_functions_match_files']['current_steps'])
            self.assertIs(payload['current_state']['membership'],False)
            self.assertIn('복지관 회원이신가요',app.subheader[0].value)
            event=next(e for e in reversed(payload['trace']) if e['phase']=='render')
            self.assertEqual(event['screen'],'membership');self.assertIs(event['state']['membership'],False)
            self.assertFalse(app.exception)

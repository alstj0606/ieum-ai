"""Both entry paths use the same member state; visual preference never answers it."""
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from services.config import Settings

APP=str(Path(__file__).resolve().parents[1]/'app.py')

class ExperimentalMembershipTest(TestCase):
    def test_both_entries_ask_membership_before_assuming_an_online_account(self):
        for entry in ('inst_start','inst_start_visual'):
            with self.subTest(entry=entry),patch('ui.seongsan_app.load_settings',return_value=Settings()):
                app=AppTest.from_file(APP,default_timeout=15).run();app.button(key=entry).click().run()
                state=app.session_state['institution_session']
                self.assertIsNone(state['membership']);self.assertIsNone(state['online_account'])
                self.assertEqual(state['guide_kind'],'application');self.assertEqual(state['index'],0)
                self.assertIn('복지관 회원이신가요',app.subheader[0].value)
                self.assertEqual(app.session_state['inst_visual_preference'],entry=='inst_start_visual')
                self.assertFalse(app.exception)

    def test_three_member_choices_match_the_rendered_outcome_from_each_entry(self):
        choices=[('inst_nonmember',False,'membership_registration','비회원 · 방문 회원등록 안내'),
                 ('inst_unknown_member',None,'membership_check','회원 여부 확인 안내'),
                 ('inst_member',True,'guide','2단계 / 6단계 · 기존 회원 · 온라인 아이디 확인')]
        for entry in ('inst_start','inst_start_visual'):
            for key,member,view,title in choices:
                with self.subTest(entry=entry,key=key),patch('ui.seongsan_app.load_settings',return_value=Settings()):
                    app=AppTest.from_file(APP,default_timeout=15).run();app.button(key=entry).click().run()
                    seq=app.session_state['institution_session']['seq'];app.button(key=key).click().run()
                    for _ in range(2):app.run()
                    state=app.session_state['institution_session']
                    self.assertIs(state['membership'],member);self.assertEqual(state['view'],view)
                    self.assertGreater(state['seq'],seq);self.assertEqual(app.subheader[0].value,title)
                    self.assertNotIn('inst_visual_guide',[t.key for t in app.toggle])
                    self.assertFalse(app.exception)

    def test_existing_member_can_choose_login_in_the_experiment(self):
        with patch('ui.seongsan_app.load_settings',return_value=Settings()):
            app=AppTest.from_file(APP,default_timeout=15).run();app.button(key='inst_start_visual').click().run()
            app.button(key='inst_member').click().run();app.button(key='inst_has_id').click().run()
            state=app.session_state['institution_session']
            self.assertTrue(state['online_account']);self.assertEqual(state['guide_kind'],'application')
            self.assertEqual(state['index'],2);self.assertIn('로그인',app.subheader[0].value)
            self.assertFalse(app.exception)

    def test_visual_preference_survives_widget_cleanup_without_changing_membership(self):
        with patch('ui.seongsan_app.load_settings',return_value=Settings()):
            app=AppTest.from_file(APP,default_timeout=15).run();app.button(key='inst_start_visual').click().run()
            app.button(key='inst_member').click().run();app.button(key='inst_no_id').click().run()
            self.assertTrue(app.toggle(key='inst_visual_guide').value)
            app.toggle(key='inst_visual_guide').set_value(False).run()
            self.assertFalse(app.session_state['inst_visual_preference'])
            app.chat_input(key='inst_chat').set_value('비회원이에요').run();app.run();app.run()
            self.assertFalse(app.session_state['institution_session']['membership'])
            self.assertNotIn('inst_visual_guide',app.session_state)
            self.assertFalse(app.session_state['inst_visual_preference'])
            app.button(key='inst_reset').click().run();app.button(key='inst_member').click().run()
            app.button(key='inst_no_id').click().run()
            self.assertFalse(app.toggle(key='inst_visual_guide').value)
            self.assertEqual(app.session_state['institution_session']['index'],0)
            self.assertFalse(app.exception)

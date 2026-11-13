"""Membership choices must render their outcome, not the original question."""
from copy import deepcopy
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from services.config import Settings
from services.institution_dialogue import load_institution, new_institution_state, guide_turn, current_steps

APP=str(Path(__file__).resolve().parents[1]/'institution_app.py')

class MembershipTransitionTest(TestCase):
    def turn(self,state,text):return guide_turn(state,text,Settings())

    def test_nonmember_outcome_uses_verified_facts_without_mutating_data(self):
        data=load_institution();before=deepcopy(data)
        state=self.turn(new_institution_state(),'복지관 비회원이에요')
        steps=current_steps(data,state)
        self.assertEqual(len(steps),1);self.assertEqual(steps[0]['step_id'],'membership_registration')
        self.assertIn('비회원',steps[0]['title']);self.assertNotIn('회원이신가요',steps[0]['title'])
        self.assertIn('전화',steps[0]['instruction']);self.assertIn(data['address'],steps[0]['details'])
        self.assertIn('공식 자료 확인 필요',steps[0]['details'])
        self.assertEqual(steps[0]['verification_source'],data['steps'][0]['verification_source'])
        self.assertEqual(data,before)

    def test_outcome_and_member_type_survive_followup_turns(self):
        for text,view,membership in [('비회원이에요','membership_registration',False),('회원 여부를 모르겠어요','membership_check',None)]:
            state=self.turn(new_institution_state(),text)
            for followup in ['다음','이전','다시 설명','못 찾겠어요']:
                state=self.turn(state,followup)
                self.assertEqual(state['view'],view);self.assertIs(state['membership'],membership)
                self.assertEqual(state['index'],0);self.assertEqual(len(current_steps(load_institution(),state)),1)
                self.assertNotIn('회원인지 먼저 확인',state['message'])

    def test_member_choice_clears_old_outcome_and_updates_member_type(self):
        state=self.turn(new_institution_state(),'비회원이에요')
        state=self.turn(state,'기존 회원이에요')
        self.assertEqual(state['member_type'],'existing_member');self.assertEqual(state['view'],'guide')
        self.assertTrue(state['membership']);self.assertEqual(state['index'],1)
        self.assertIn('기존 회원',current_steps(load_institution(),state)[1]['title'])
        state=self.turn(state,'온라인 아이디가 있어요')
        self.assertEqual((state['index'],state['member_type']),(2,'existing_online'))

    def test_signup_and_membership_outcomes_never_share_step_index(self):
        state=self.turn(new_institution_state(),'복지관 회원이고 아이디가 없어요')
        for _ in range(3):state=self.turn(state,'다음')
        state=self.turn(state,'비회원이에요')
        self.assertEqual((state['guide_kind'],state['index']),('application',0))
        state=self.turn(state,'온라인 아이디 만들기')
        self.assertEqual(state['view'],'membership_registration');self.assertFalse(state['membership'])
        state=self.turn(state,'회원 여부를 모르겠어요')
        self.assertEqual(current_steps(load_institution(),state)[0]['step_id'],'membership_check')
        state=self.turn(state,'복지관 회원이고 아이디가 없어요')
        self.assertEqual((state['guide_kind'],state['index'],state['view']),('signup',0,'guide'))
        self.assertEqual(len(current_steps(load_institution(),state)),5)

    def test_streamlit_outcomes_rerun_change_type_and_visual_isolation(self):
        with patch('ui.seongsan_app.load_settings',return_value=Settings()):
            app=AppTest.from_file(APP,default_timeout=15).run()
            app.button(key='inst_start').click().run()
            for key,title,view in [('inst_nonmember','비회원 · 방문 회원등록 안내','membership_registration'),('inst_unknown_member','회원 여부 확인 안내','membership_check')]:
                app.button(key=key).click().run();app.run()
                self.assertFalse(app.exception);self.assertEqual(app.subheader[0].value,title)
                self.assertEqual(app.session_state['institution_session']['view'],view)
                self.assertNotIn('inst_nonmember',[b.key for b in app.button])
                self.assertNotIn('inst_next',[b.key for b in app.button])
                app.button(key='inst_stuck').click().run()
                self.assertEqual(app.subheader[0].value,title)
                details=current_steps(load_institution(),app.session_state['institution_session'])[0]['details']
                self.assertEqual(sum(m.value==details for m in app.markdown),1)
                app.button(key='inst_reset').click().run()
            app.button(key='inst_member').click().run();app.run()
            self.assertIn('기존 회원',app.subheader[0].value)
            app.button(key='inst_no_id').click().run()
            app.toggle(key='inst_visual_guide').set_value(True).run()
            for _ in range(2):app.button(key='inst_next').click().run()
            app.chat_input(key='inst_chat').set_value('비회원이에요').run();app.run()
            self.assertEqual(app.subheader[0].value,'비회원 · 방문 회원등록 안내')
            self.assertNotIn('inst_visual_guide',[t.key for t in app.toggle])
            app.button(key='inst_reset').click().run()
            app.button(key='inst_member').click().run();app.button(key='inst_no_id').click().run()
            self.assertEqual(app.session_state['institution_session']['index'],0)
            self.assertFalse(app.exception)

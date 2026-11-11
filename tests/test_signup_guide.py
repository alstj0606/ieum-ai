"""Verified signup boundary, member branches, session and provider-failure regressions."""
from copy import deepcopy
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock,patch
from streamlit.testing.v1 import AppTest
from services.config import Settings
from services.institution_dialogue import guide_turn,new_institution_state,load_institution,current_steps,rule_action

APP=str(Path(__file__).resolve().parents[1]/'app.py')
class SignupGuideTest(TestCase):
 def turn(self,s,text,action=None):return guide_turn(s,text,Settings(),action=action)
 def signup(self):return self.turn(new_institution_state(),'복지관 회원이고 아이디가 없어요')
 def test_provenance_and_verified_boundary(self):
  d=load_institution();steps=d['signup_steps'];self.assertEqual(len(steps),5)
  for step in steps:
   self.assertEqual(step['verified_at'],'2026-11-11');self.assertEqual(step['verification_origin'],'user_report');self.assertEqual(step['verified_device'],'iPad Safari')
   self.assertEqual(step['official_url'],'https://sssenior.e-ncom.co.kr/');self.assertIsNone(step['screenshot_path']);self.assertIsNone(step['arrow_target'])
  self.assertIn('이후 화면',steps[-1]['details']);self.assertIn('미검증',steps[-1]['details']);self.assertEqual(d['registration_status'],'unknown')
 def test_start_navigation_and_terminal_no_completion_claim(self):
  s=self.signup();self.assertTrue(s['membership']);self.assertEqual(s['guide_kind'],'signup');self.assertEqual(s['member_type'],'new_online')
  for index in range(5):
   self.assertEqual(s['index'],index);s=self.turn(s,'다음')
  self.assertEqual(s['index'],4);self.assertIn('미검증',s['message']);self.assertNotIn('completed',s)
  s=self.turn(s,'이전');self.assertEqual(s['index'],3)
 def test_unknown_and_nonmember_are_not_promoted_by_no_id(self):
  s=self.turn(new_institution_state(),'아이디가 없어요');self.assertIsNone(s['membership']);self.assertEqual(s['guide_kind'],'signup')
  s=self.turn(s,'다음');self.assertEqual(s['index'],0)
  s=self.turn(s,'비회원이에요');self.assertFalse(s['membership']);self.assertEqual(s['guide_kind'],'application')
  s=self.turn(s,'온라인 아이디 만들기');self.assertFalse(s['membership']);self.assertEqual(s['index'],0);self.assertIn('방문',s['message'])
 def test_four_member_branches(self):
  a=self.turn(new_institution_state(),'복지관 회원이고 온라인 아이디가 있어요');self.assertEqual((a['member_type'],a['index'],a['guide_kind']),('existing_online',2,'application'))
  b=self.signup();self.assertEqual((b['member_type'],b['index'],b['guide_kind']),('new_online',0,'signup'))
  c=self.turn(b,'복지관 비회원이에요');self.assertEqual(c['member_type'],'nonmember');self.assertIn('준비 서류',c['message'])
  d=self.turn(b,'회원 여부를 모르겠어요');self.assertEqual(d['member_type'],'unknown');self.assertIsNone(d['membership']);self.assertIn('055-714-9178',d['message'])
 def test_stuck_uses_only_current_verified_location(self):
  s=self.signup();data=load_institution()
  for index,word in [(1,'상단'),(2,'아래쪽'),(3,'체크박스'),(4,'영역')]:
   s['index']=index;s=self.turn(s,'아이디 만들기 버튼을 못 찾겠어요')
   self.assertEqual(s['index'],index);self.assertEqual(s['message'],data['signup_steps'][index]['help_text']);self.assertIn(word,s['message'])
   self.assertNotIn('results',s)
 def test_repeat_reset_and_type_change(self):
  s=self.signup();s['index']=3;s=self.turn(s,'다시 설명');self.assertIn('회원가입약관',s['message']);self.assertEqual(s['index'],3)
  s=self.turn(s,'온라인 아이디가 있어요');self.assertEqual(s['guide_kind'],'application');self.assertEqual(s['index'],2)
  s=self.turn(s,'처음으로');self.assertIsNone(s['membership']);self.assertIsNone(s['online_account']);self.assertEqual(s['index'],0)
 def test_signup_problem_keeps_current_verified_help(self):
  s=self.signup();s['index']=3;s=self.turn(s,'회원가입이 안 돼요')
  self.assertEqual(s['index'],3);self.assertEqual(s['message'],load_institution()['signup_steps'][3]['help_text'])
  self.assertNotEqual(rule_action('기존 회원인데 아이디 만들기를 못 찾겠어요'),'member_with_id')
 def test_agreement_is_not_a_completed_fact(self):
  s=self.signup();s['index']=3;s=self.turn(s,'다음');self.assertEqual(s['index'],4)
  self.assertNotIn('terms_accepted',s);self.assertNotIn('authenticated',s)
  self.assertIn('직접 결정',load_institution()['signup_steps'][3]['help_text'])
 def test_api_failure_keeps_signup_step_and_help(self):
  s=self.signup();s['index']=2;client=Mock();client.models.generate_content.side_effect=TimeoutError('private-error')
  s=guide_turn(s,'아이디 만들기 버튼을 못 찾겠어요',Settings(gemini_api_key='mock'),client=client)
  self.assertEqual(s['index'],2);self.assertEqual(s['mode'],'fallback');self.assertIn('아래쪽',s['message']);self.assertNotIn('private-error',str(s))
 def test_identifier_not_sent_to_ai_or_kept_in_history(self):
  s=self.signup();client=Mock()
  s=guide_turn(s,'아이디: secret-user-name',Settings(gemini_api_key='mock'),client=client)
  client.models.generate_content.assert_not_called();self.assertNotIn('secret-user-name',str(s));self.assertIn('입력하지 마세요',s['message'])
 def test_script_runner_new_flow_rerun_and_return(self):
  with patch('ui.seongsan_app.load_settings',return_value=Settings()):
   a=AppTest.from_file(APP,default_timeout=15).run();a.button(key='inst_start').click().run();a.button(key='inst_member').click().run();a.button(key='inst_no_id').click().run()
   self.assertFalse(a.exception);self.assertEqual(a.session_state['institution_session']['guide_kind'],'signup')
   a.button(key='inst_next').click().run();a.run();self.assertEqual(a.session_state['institution_session']['index'],1)
   a.button(key='inst_stuck').click().run();self.assertIn('상단',a.session_state['institution_session']['message'])
   a.button(key='inst_repeat').click().run()
   instruction=current_steps(load_institution(),a.session_state['institution_session'])[1]['instruction']
   self.assertEqual(sum(instruction in m.value for m in a.markdown),1)
   a.button(key='inst_previous').click().run();self.assertEqual(a.session_state['institution_session']['index'],0)
   a.button(key='inst_reset').click().run();self.assertEqual(a.session_state['institution_session']['guide_kind'],'application');self.assertFalse(a.exception)

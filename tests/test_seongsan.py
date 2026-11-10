"""Institution scope/gates/intent firewall and routed Streamlit startup. All AI mocked."""
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import TestCase
from unittest.mock import Mock,patch
from streamlit.testing.v1 import AppTest
from services.config import Settings
from services.institution_dialogue import *

APP=str(Path(__file__).resolve().parents[1]/'app.py')
class SeongsanTest(TestCase):
 def turn(self,s,text,**kw):return guide_turn(s,text,Settings(),**kw)
 def member(self):return self.turn(new_institution_state(),'기존 회원이에요')
 def test_data_contract_and_unknown_programs(self):
  d=load_institution();self.assertEqual(len(d['steps']),6);self.assertEqual(d['registration_status'],'unknown');self.assertEqual(d['current_programs'],[])
  for x in d['steps']:
   self.assertEqual(x['institution_id'],d['institution_id']);self.assertIn(x['site_id'],d['sites']);self.assertIn(x['verification_level'],LEVELS);self.assertIsNone(x['screenshot_path']);self.assertIsNone(x['arrow_target'])
  self.assertTrue(all(x['verification_level']=='로그인 이후 미확인' for x in d['steps'][3:]))
 def test_member_gate_and_nonmember_never_bypassed(self):
  s=self.turn(new_institution_state(),'다음');self.assertEqual(s['index'],0)
  s=self.turn(s,'비회원이에요');self.assertFalse(s['membership']);self.assertIn('방문',s['message'])
  s=self.turn(s,'다음');self.assertEqual(s['index'],0)
  s=self.turn(s,'기존 회원이에요');self.assertTrue(s['membership']);self.assertEqual(s['index'],1)
 def test_next_previous_stuck_keep_current_context(self):
  s=self.member();s=self.turn(s,'다음');s=self.turn(s,'다음');self.assertEqual(s['index'],3)
  before=deepcopy(s);s=self.turn(s,'수강신청 버튼을 못 찾겠어요');self.assertEqual(s['index'],3);self.assertIn('수강신청 및 결제',s['message']);self.assertNotIn('results',s);self.assertEqual(before['index'],3)
  s=self.turn(s,'이전');self.assertEqual(s['index'],2);s=self.turn(s,'로그인이 어려워요');self.assertEqual(s['index'],2)
  s=self.turn(s,'로그인했는데 다음에 뭘 해야 해요');self.assertEqual(s['index'],3)
 def test_membership_help_does_not_claim_welfare_membership(self):
  s=self.turn(new_institution_state(),'회원가입이 안 돼요');self.assertIsNone(s['membership']);self.assertIn('본인인증',s['message']);self.assertIn('방문 회원등록',s['message'])
 def test_no_reservation_completion_and_no_current_schedule(self):
  s=self.member()
  for _ in range(8):s=self.turn(s,'다음')
  self.assertEqual(s['index'],5)
  for text in ('신청 완료됐나요','추첨 당첨인가요','결제는 어떻게 해요','지금 모집중이에요'):
   s=self.turn(s,text);self.assertEqual(s['index'],5);self.assertTrue('미확인' in s['message'] or '확인할 수 없어요' in s['message']);self.assertNotIn('booked',s)
 def test_reset_clears_membership_and_stage(self):
  s=self.member();s=self.turn(s,'다음');s=self.turn(s,'처음부터 다시');self.assertEqual(s['index'],0);self.assertIsNone(s['membership'])
 def test_ai_failure_keeps_stage_and_does_not_leak_error(self):
  s=self.member();s['index']=3;client=Mock();client.models.generate_content.side_effect=TimeoutError('private-canary')
  s=guide_turn(s,'수강신청 버튼을 못 찾겠어요',Settings(gemini_api_key='mock'),client=client)
  self.assertEqual(s['index'],3);self.assertEqual(s['mode'],'fallback');self.assertEqual(s['diagnostic'],'timeout');self.assertIn('기본 안내',s['notice']);self.assertNotIn('private-canary',str(s))
 def test_ai_success_only_action_no_facts(self):
  client=Mock();client.models.generate_content.return_value=NS(text=json.dumps({'action':'stuck'}),prompt_feedback=None,candidates=[NS(finish_reason='STOP')])
  s=self.member();s['index']=3;s=guide_turn(s,'그거 어딨는지 도통 모르겠네',Settings(gemini_api_key='mock'),client=client)
  self.assertEqual(s['mode'],'gemini');self.assertEqual(s['index'],3);self.assertIn('수강신청 및 결제',s['message'])
  args=client.models.generate_content.call_args.kwargs;self.assertEqual(args['model'],'gemini-2.5-flash');self.assertNotIn('history',json.loads(args['contents']))
 def test_ai_cannot_forge_membership_or_override_explicit_stuck(self):
  client=Mock();client.models.generate_content.return_value=NS(text=json.dumps({'action':'member'}),prompt_feedback=None,candidates=[NS(finish_reason='STOP')])
  s=guide_turn(new_institution_state(),'회원가입이 안돼요',Settings(gemini_api_key='mock'),client=client);self.assertIsNone(s['membership']);self.assertEqual(s['index'],0)
  client.models.generate_content.return_value.text=json.dumps({'action':'next'});s=self.member();s['index']=3
  s=guide_turn(s,'못 찾겠어요',Settings(gemini_api_key='mock'),client=client);self.assertEqual(s['index'],3)
 def test_generated_text_or_url_is_rejected(self):
  client=Mock();client.models.generate_content.return_value=NS(text=json.dumps({'action':'stuck','url':'https://invented.invalid'}),prompt_feedback=None,candidates=[NS(finish_reason='STOP')])
  s=guide_turn(self.member(),'모르겠네요',Settings(gemini_api_key='mock'),client=client);self.assertEqual(s['mode'],'fallback');self.assertNotIn('invented',str(s))
 def test_sensitive_value_not_sent_or_stored(self):
  client=Mock();s=guide_turn(self.member(),'인증번호는 123456',Settings(gemini_api_key='mock'),client=client)
  client.models.generate_content.assert_not_called();self.assertNotIn('123456',str(s));self.assertIn('입력하지 마세요',s['message'])
 def test_first_screen_four_actions_no_gangseo_cards(self):
  with patch('ui.seongsan_app.load_settings',return_value=Settings()):
   a=AppTest.from_file(APP,default_timeout=10).run();self.assertFalse(a.exception)
   for key in ('inst_programs','inst_start','inst_membership'):self.assertIsNotNone(a.button(key=key))
   self.assertNotIn('dialog',a.session_state);a.button(key='inst_start').click().run();self.assertEqual(a.session_state['institution_session']['index'],0)
   a.chat_input(key='inst_chat').set_value('다음').run();self.assertEqual(a.session_state['institution_session']['index'],0)
 def test_ui_navigation_rerun_and_legacy_roundtrip(self):
  with patch('ui.seongsan_app.load_settings',return_value=Settings()),patch('services.config.load_settings',return_value=Settings()):
   a=AppTest.from_file(APP,default_timeout=10).run();a.button(key='inst_start').click().run();a.button(key='inst_member').click().run();a.button(key='inst_next').click().run();a.run()
   self.assertEqual(a.session_state['institution_session']['index'],2)
   a.chat_input(key='inst_chat').set_value('못 찾겠어요').run();self.assertEqual(a.session_state['institution_session']['index'],2)
   a.button(key='open_gangseo').click().run();self.assertFalse(a.exception);a.chat_input(key='chat').set_value('강서구 걷기 프로그램 찾아줘').run();self.assertEqual(a.session_state['dialog']['alternatives'][0]['activity_type'],'슬로우조깅')
   a.button(key='back_to_seongsan').click().run();self.assertEqual(a.session_state['institution_session']['index'],2);self.assertFalse(a.exception)

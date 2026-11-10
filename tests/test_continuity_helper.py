"""Session continuity and source-backed guidance, no live provider/site submissions."""
import ast
import importlib
import json
from copy import deepcopy
from datetime import date
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import TestCase
from unittest.mock import Mock,patch
from streamlit.testing.v1 import AppTest
from services.activities import load_activities
from services.application_helper import helper_view,start_helper,move_helper,load_guides,helper_speech
from services.config import Settings
from services.dialogue import new_state,handle_turn,application_guide,choose_alternative,basic_extract
from services.recommendation_pipeline import prepare_view
from services.continuity import recommended_rows

DAY=date(2026,11,10);APP=str(Path(__file__).resolve().parents[1]/'gangseo_app.py')
PROFILE='65세이고 강서구에서 가볍게 운동하고 싶어요.'
PARK='seonam-parkgolf-reservation-2026';SLOW='gangseo-slow-jogging-2026-h2-40plus';ACADEMY='seoul-renewal-academy-gangseo-20261121'
class ContinuityHelperTest(TestCase):
 def setUp(self):self.rows=load_activities();self.byid={r['id']:r for r in self.rows}
 def turn(self,s,text,**kw):return handle_turn(s,text,self.rows,Settings(),as_of=DAY,**kw)
 def initial(self):return self.turn(new_state(),PROFILE)
 def start(self):return application_guide(self.initial(),self.rows,selected_id=PARK,as_of=DAY)
 def test_same_result_has_delta_explanation_and_does_not_mutate_previous(self):
  first=self.initial();snapshot=deepcopy(first);second=self.turn(first,'오후가 좋아요.')
  self.assertEqual(first,snapshot);self.assertTrue(second['recommendation_update']['same'])
  self.assertTrue(second['recommendation_update']['hide_repeated_cards'])
  self.assertEqual(second['conditions']['age'],65);self.assertEqual(second['conditions']['region'],'강서구')
  for text in ('새 조건','유지한 조건','앞서 안내한 활동과 순서는 같아요','공식 자료에 오후 회차','자격과 빈자리'):self.assertIn(text,second['message'])
  self.assertEqual(second['history'][-1]['content'],second['message'])
  self.assertNotIn('확인한 공식 자료에서 활동을 찾았어요',second['message'])
 def test_selected_program_and_guide_survive_followup_and_view_reruns(self):
  s=move_helper(self.start(),self.rows,'next',as_of=DAY)
  next_state=self.turn(s,'오후가 좋아요')
  for _ in range(3):next_state=prepare_view(next_state,self.rows,user_text='오후가 좋아요',as_of=DAY)
  self.assertEqual(next_state['selected_id'],PARK);self.assertEqual(next_state['application_helper']['index'],1)
  self.assertFalse(next_state.get('helper_focus'));self.assertEqual(next_state['last_recommendation']['selected_id'],PARK)
 def test_mandatory_free_explains_removed_program_and_discards_invalid_selection(self):
  s=self.turn(self.start(),'오후가 좋아요');s=self.turn(s,'무료로 찾아줘')
  self.assertEqual(s['condition_modes']['budget_amount'],'required');self.assertEqual(s['conditions']['time_slot'],'오후')
  self.assertFalse(s['recommendation_update']['same']);self.assertIn('무료 예산을 필수로',s['message']);self.assertIn('바뀐 조건에 맞는 결과에서 빠졌어요',s['message'])
  self.assertNotIn(PARK,[r['id'] for r in recommended_rows(s)]);self.assertIsNone(s['selected_id']);self.assertNotIn('application_helper',s)
 def test_unknown_time_never_claims_afternoon(self):
  rows=deepcopy(self.rows);r=next(x for x in rows if x['id']==PARK);r['schedule']['time_slots']=[];r['schedule']['text']='일정 확인 필요'
  first=handle_turn(new_state(),PROFILE,rows,Settings(),as_of=DAY)
  second=handle_turn(first,'오후가 좋아요',rows,Settings(),as_of=DAY)
  self.assertIn('오후 운영 여부가 확인되지 않았어요',second['message']);self.assertNotIn('공식 자료에 오후 회차',second['message'])
 def test_gemini_success_and_failure_have_same_continuity_contract(self):
  states=[]
  for fail in (False,True):
   client=Mock();state=new_state()
   for text in (PROFILE,'오후가 좋아요'):
    payload=basic_extract(text,state)
    if fail:client.models.generate_content.side_effect=TimeoutError('private-provider-canary')
    else:client.models.generate_content.return_value=NS(text=json.dumps(payload),prompt_feedback=None,candidates=[NS(finish_reason='STOP')])
    state=handle_turn(state,text,self.rows,Settings(gemini_api_key='mock'),client=client,as_of=DAY)
   self.assertEqual(state['mode'],'fallback' if fail else 'gemini');self.assertEqual(state['conditions']['age'],65)
   self.assertTrue(state['recommendation_update']['same']);self.assertNotIn('private-provider-canary',str(state))
   if fail:self.assertIn('기본 규칙',state['notice'])
   states.append(state)
  self.assertEqual(states[0]['message'],states[1]['message'])
 def test_time_clear_and_required_mode_change_are_followups(self):
  s=self.turn(self.initial(),'오후가 좋아요');s=self.turn(s,'오후로 찾아줘')
  self.assertEqual(s['condition_modes']['time_slot'],'required');self.assertIn('시간을 필수로 적용',s['message'])
  s=self.turn(s,'시간은 상관없어요');self.assertNotIn('time_slot',s['conditions']);self.assertIn('시간 조건을 풀었어요',s['message'])
 def test_online_steps_use_verified_source_and_bound_navigation(self):
  s=self.start();self.assertEqual(s['application_helper']['index'],0)
  self.assertTrue(s['helper_focus']);self.assertEqual(s['selected_id'],PARK)
  for index in range(5):
   v=helper_view(self.byid[PARK],s['conditions'],s['application_helper'],as_of=DAY)
   self.assertEqual(v['index'],index);self.assertEqual(v['total'],5);self.assertIn(v['step']['source_url'],[self.byid[PARK]['source_url'],load_guides()[PARK]['help_url']])
   self.assertIn('실제 신청 완료 여부',helper_speech(v));s=move_helper(s,self.rows,'next',as_of=DAY)
  self.assertEqual(s['application_helper']['index'],4)
  s=move_helper(s,self.rows,'previous',as_of=DAY);self.assertEqual(s['application_helper']['index'],3)
  before=helper_view(self.byid[PARK],s['conditions'],s['application_helper'],as_of=DAY)['step']
  s=move_helper(s,self.rows,'repeat',as_of=DAY);self.assertEqual(helper_view(self.byid[PARK],s['conditions'],s['application_helper'],as_of=DAY)['step'],before)
 def test_program_change_resets_helper_and_selection(self):
  s=move_helper(self.start(),self.rows,'next',as_of=DAY);s=self.turn(s,'강서구 국악 공연 보고 싶어요')
  self.assertNotIn('application_helper',s);self.assertIsNone(s['selected_id'])
  s=application_guide(s,self.rows,as_of=DAY);self.assertNotEqual(s['application_helper']['program_id'],PARK);self.assertEqual(s['application_helper']['index'],0)
 def test_closed_selection_only_has_next_recruitment_checks(self):
  s=self.turn(new_state(),'강서구 걷기 프로그램 찾아줘');s=choose_alternative(s,'슬로우조깅',self.rows,Settings(),as_of=DAY)
  s=application_guide(s,self.rows,selected_id=SLOW,as_of=DAY)
  self.assertEqual(s['code'],'closed');self.assertFalse(s['results'])
  v=helper_view(self.byid[SLOW],s['conditions'],s['application_helper'],as_of=DAY)
  self.assertEqual(v['mode'],'closed');self.assertEqual(v['next_date'],'다음 접수 일정 미정');self.assertIn('마감',v['step']['title'])
  s=move_helper(s,self.rows,'next',as_of=DAY);v=helper_view(self.byid[SLOW],s['conditions'],s['application_helper'],as_of=DAY)
  self.assertEqual(v['step']['site_labels'],'목록보기');self.assertNotIn('예약하기',v['step']['action'])
 def test_new_status_rechecks_and_clears_old_progress(self):
  s=self.start();s['application_helper'].update(index=4,finished_reading=True)
  s=move_helper(s,self.rows,'repeat',as_of=date(2027,1,2))
  self.assertEqual(s['application_helper']['mode'],'closed');self.assertEqual(s['application_helper']['index'],0);self.assertFalse(s['application_helper'].get('finished_reading'))
 def test_reading_finished_does_not_claim_reservation_complete(self):
  s=self.start();s['application_helper']['index']=4;s=move_helper(s,self.rows,'finish',as_of=DAY)
  self.assertTrue(s['application_helper']['finished_reading']);self.assertNotIn('reservation_complete',s);self.assertNotIn('booked',s)
 def test_phone_is_inquiry_and_visit_unknown_fields_not_invented(self):
  v=helper_view(self.byid[ACADEMY],{},as_of=DAY)
  self.assertTrue(v['channels']['online']);self.assertTrue(v['channels']['visit']);self.assertFalse(v['channels']['phone'])
  self.assertEqual(v['contact']['phone'],'02-464-4114');self.assertEqual(v['contact']['role'],'inquiry')
  for key in ('reception_desk','materials','hours'):self.assertIsNone(v['visit'][key])
  self.assertEqual(v['visit']['address'],self.byid[ACADEMY]['address']);self.assertEqual(v['mode'],'unverified')
 def test_other_programs_do_not_borrow_verified_button_steps(self):
  for row in self.rows:
   v=helper_view(row,{},as_of=DAY)
   if row['id']!=PARK:self.assertNotEqual(v['mode'],'online')
  aqua=self.byid['gonghang-aqua-reference-20250805'];v=helper_view(aqua,{},as_of=DAY)
  self.assertEqual(v['mode'],'check');self.assertFalse(any(v['channels'].values()));self.assertIsNone(v['contact'])
 def test_eligibility_failure_blocks_online_guide(self):
  row=deepcopy(self.byid[PARK]);row['id']=SLOW
  v=helper_view(row,{'age':20},as_of=DAY);self.assertEqual(v['mode'],'blocked')
 def test_app_import_contract(self):
  imports=[node for node in ast.walk(ast.parse(Path(APP).read_text())) if isinstance(node,ast.ImportFrom) and node.module and node.module.startswith('services.')]
  for node in imports:
   module=importlib.import_module(node.module)
   for name in node.names:self.assertTrue(hasattr(module,name.name),(node.module,name.name))
 def test_app_rerun_keeps_profile_and_compact_followup(self):
  with patch('services.config.load_settings',return_value=Settings()):
   a=AppTest.from_file(APP,default_timeout=10).run();a.chat_input(key='chat').set_value(PROFILE).run()
   a.run();first=a.session_state['dialog'];self.assertEqual(first['conditions']['age'],65)
   a.chat_input(key='chat').set_value('오후가 좋아요').run();a.run()
   self.assertFalse(a.exception);self.assertEqual(a.session_state['dialog']['conditions']['age'],65)
   self.assertTrue(a.session_state['dialog']['recommendation_update']['same']);self.assertEqual(len(a.chat_message[-1].subheader),0)
   self.assertTrue(any('앞서 안내한 활동' in x.value for x in a.chat_message[-1].markdown))
 def test_app_online_buttons_rerun_repeat_and_resume(self):
  with patch('services.config.load_settings',return_value=Settings()):
   a=AppTest.from_file(APP,default_timeout=10).run();a.chat_input(key='chat').set_value(PROFILE).run();a.button(key='apply_'+PARK).click().run()
   self.assertFalse(a.exception);self.assertTrue(a.session_state['dialog']['helper_focus'])
   a.button(key='helper_next').click().run();a.run();self.assertEqual(a.session_state['dialog']['application_helper']['index'],1)
   a.button(key='helper_previous').click().run();self.assertEqual(a.session_state['dialog']['application_helper']['index'],0)
   a.button(key='helper_repeat').click().run();self.assertEqual(a.session_state['dialog']['application_helper']['index'],0)
   a.chat_input(key='chat').set_value('오후가 좋아요').run();self.assertEqual(a.session_state['dialog']['selected_id'],PARK)
   a.button(key='helper_resume').click().run();self.assertTrue(a.session_state['dialog']['helper_focus']);self.assertFalse(a.exception)
 def test_application_steps_chat_navigation_does_not_call_gemini(self):
  client=Mock();s=self.start();s=handle_turn(s,'다음 단계',self.rows,Settings(gemini_api_key='mock'),client=client,as_of=DAY)
  self.assertEqual(s['application_helper']['index'],1);client.models.generate_content.assert_not_called()
  s=self.turn(s,'신청 방법 알려줘');self.assertEqual(s['application_helper']['index'],1)
 def test_repeated_preference_does_not_reprint_full_recommendations(self):
  first=self.turn(self.initial(),'오후가 좋아요');second=self.turn(first,'오후가 좋아요')
  self.assertTrue(second['recommendation_update']['hide_repeated_cards']);self.assertEqual(second['conditions'],first['conditions']);self.assertIn('시간 조건은 그대로예요',second['message'])
 def test_guide_data_has_official_provenance_and_invalid_steps_are_rejected(self):
  from tempfile import TemporaryDirectory
  guides=load_guides()
  for key,guide in guides.items():
   self.assertIn(key,self.byid);self.assertEqual(guide['source_url'],self.byid[key]['source_url']);self.assertEqual(guide['verified_at'],'2026-11-10')
   self.assertFalse(guide['phone_application'])
  with TemporaryDirectory() as tmp:
   path=Path(tmp)/'bad.json';bad=deepcopy(guides);bad[PARK]['steps'][0].pop('source_url');path.write_text(json.dumps(bad))
   with self.assertRaises(ValueError):load_guides(path)
 def test_unreadable_guide_degrades_without_inventing_steps(self):
  with patch('services.application_helper.load_guides',side_effect=ValueError('not displayed')):
   v=helper_view(self.byid[PARK],{},as_of=DAY)
  self.assertEqual(v['mode'],'unverified');self.assertIsNone(v['step']['site_labels']);self.assertNotIn('not displayed',str(v))
 def test_tts_reads_current_step_and_compact_update_not_old_long_cards(self):
  with patch('services.config.load_settings',return_value=Settings(api_key='mock-voice-only')),patch('services.voice.synthesize',return_value=b'mock-audio') as voice:
   a=AppTest.from_file(APP,default_timeout=10).run();a.chat_input(key='chat').set_value(PROFILE).run();a.chat_input(key='chat').set_value('오후가 좋아요').run()
   index=len(a.session_state['turns'])-1;a.button(key='listen_'+str(index)).click().run()
   compact=voice.call_args.args[0];self.assertIn('앞서 안내한 활동과 순서는 같아요',compact);self.assertNotIn('안내할 활동은',compact)
   a.button(key='compact_helper').click().run();a.button(key='helper_next').click().run();index=len(a.session_state['turns'])-1
   a.button(key='listen_'+str(index)).click().run();step=voice.call_args.args[0];self.assertIn('2단계, 전체 5단계',step);self.assertIn('공식 사이트에서 로그인 버튼',step);self.assertNotIn('안내할 활동은',step)
 def test_chat_application_request_preserves_newly_selected_guide(self):
  s=self.turn(self.initial(),'신청 도와주세요')
  self.assertEqual(s['selected_id'],PARK);self.assertTrue(s['helper_focus']);self.assertEqual(s['application_helper']['program_id'],PARK)
  with patch('services.config.load_settings',return_value=Settings()):
   a=AppTest.from_file(APP,default_timeout=10).run();a.chat_input(key='chat').set_value(PROFILE).run();a.chat_input(key='chat').set_value('신청 도와주세요').run()
   self.assertFalse(a.exception);self.assertTrue(a.session_state['dialog']['helper_focus']);self.assertEqual(a.session_state['dialog']['application_helper']['index'],0)

 def test_trying_exercise_does_not_turn_into_spectator_purpose(self):
  s=self.turn(new_state(),'65세 강서구에서 가볍게 운동해보고 싶어요')
  self.assertEqual(s['conditions']['purpose'],'운동');self.assertTrue(s['results'])

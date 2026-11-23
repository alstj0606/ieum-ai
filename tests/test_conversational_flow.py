"""Acceptance/refusal follows the same verified candidates for all API modes."""
from copy import deepcopy
from datetime import date
from unittest import TestCase
from unittest.mock import patch
from pathlib import Path
from streamlit.testing.v1 import AppTest
from services.activities import load_activities
from services.config import Settings
from services.dialogue import new_state
from services.discovery import discovery_turn,visible_activities,return_to_recommendations
from services.recommendation_pipeline import prepare_view
from services.ai import AIError

DAY=date(2026,11,23)
class ConversationTest(TestCase):
 def setUp(self):self.rows=load_activities()
 def turn(self,state,text,**kw):return discovery_turn(state,text,self.rows,Settings(),as_of=DAY,**kw)[0]
 def test_activity_region_accept_details_back_and_application(self):
  s=self.turn(new_state(),'수영을 배우고 싶어요');self.assertEqual(s['pending'],'region')
  s=self.turn(s,'서울 강서구요');self.assertNotEqual(s['pending'],'region')
  ids=[r['id'] for r in visible_activities(s)];self.assertTrue(ids)
  picked=self.turn(s,'좋아요');self.assertTrue(picked['detail_focus']);self.assertEqual(picked['selected_id'],ids[0])
  back=return_to_recommendations(picked);self.assertEqual([r['id'] for r in visible_activities(back)],ids)
  self.assertIsNone(back['selected_id']);self.assertEqual(back['conditions']['region'],'강서구')
  guide=self.turn(picked,'신청 방법 알려줘');self.assertTrue(guide.get('application_helper'));self.assertNotIn('신청 완료',guide['message'])
 def test_multi_accept_requests_selection_instead_of_guessing(self):
  s=self.turn(new_state(),'강서구 문화 행사 찾아줘');self.assertGreater(len(visible_activities(s)),1)
  accepted=self.turn(s,'좋아요');self.assertEqual(accepted['pending'],'selection');self.assertIsNone(accepted['selected_id'])
  second=self.turn(accepted,'2번');self.assertEqual(second['selected_id'],visible_activities(s)[1]['id'])
  self.assertTrue(second['detail_focus'])
 def test_invalid_selection_cannot_select_first_implicitly(self):
  s=self.turn(new_state(),'강서구 수영 프로그램');wrong=self.turn(s,'3번');self.assertEqual(wrong['code'],'choose');self.assertIsNone(wrong['selected_id'])
 def test_refuse_excludes_previous_cards_from_search_and_final_render(self):
  s=self.turn(new_state(),'강서구 문화 행사 찾아줘');old={r['id'] for r in visible_activities(s)}
  rejected=self.turn(s,'다른 거 추천해 줘');new={r['id'] for r in visible_activities(rejected)}
  self.assertFalse(old&new);self.assertTrue(old<=set(rejected['declined_ids']))
  final=prepare_view(rejected,self.rows,user_text='다른 거 추천해 줘',as_of=DAY)
  self.assertFalse(old&{r['id'] for r in visible_activities(final)})
  self.assertEqual(rejected['conditions']['region'],'강서구');self.assertEqual(rejected.get('search_scope',{}).get('kind'),'local')
 def test_exhausted_candidates_ask_one_condition_without_region_expansion(self):
  s=self.turn(new_state(),'강서구 수영 프로그램');s=self.turn(s,'마음에 안 들어')
  self.assertFalse(visible_activities(s));self.assertEqual(s['pending'],'refine');self.assertEqual(s['message'].count('?'),1)
  s=self.turn(s,'인접 지역도 찾아줘');self.assertEqual(s['pending'],'expand_region')
  no=self.turn(s,'아니요');self.assertNotEqual(no['flow'],'adjacent')
  yes=self.turn(s,'네');self.assertEqual(yes['flow'],'adjacent');self.assertFalse(visible_activities(yes))
 def test_refusal_keeps_explicit_time_budget_and_reset_clears_history(self):
  s=self.turn(new_state(),'강서구 무료 문화 활동');s=self.turn(s,'오후가 좋아요')
  previous=deepcopy(s['conditions']);s=self.turn(s,'다른 거 추천해 줘');self.assertEqual(s['conditions'],previous)
  s=self.turn(s,'처음부터 다시');self.assertFalse(s.get('declined_ids'));self.assertFalse(s['conditions'])
 def test_api_success_and_error_share_refusal_and_selection(self):
  from services.dialogue import basic_extract
  for error in (False,True):
   request=basic_extract('강서구 수영 프로그램',new_state())
   with patch('services.dialogue.extract_conditions',side_effect=AIError(code='timeout') if error else None,return_value=request) as provider:
    s=discovery_turn(new_state(),'강서구 수영 프로그램',self.rows,Settings(gemini_api_key='mock'),as_of=DAY)[0]
    self.assertEqual(s['mode'],'fallback' if error else 'gemini')
    picked=discovery_turn(s,'좋아요',self.rows,Settings(gemini_api_key='mock'),as_of=DAY)[0]
    self.assertTrue(picked['detail_focus']);provider.assert_called_once()
    rejected=discovery_turn(picked,'마음에 안 들어',self.rows,Settings(gemini_api_key='mock'),as_of=DAY)[0]
    self.assertFalse(visible_activities(rejected));provider.assert_called_once()
 def test_api_timeout_before_refusal_is_not_disguised(self):
  with patch('services.dialogue.extract_conditions',side_effect=AIError(code='timeout')):
   s=discovery_turn(new_state(),'강서구 수영',self.rows,Settings(gemini_api_key='mock'),as_of=DAY)[0]
  self.assertEqual(s['mode'],'fallback');s=self.turn(s,'다른 거 추천해 줘');self.assertEqual(s['diagnostic']['code'],'timeout');self.assertIn('기본 규칙',s['notice'])
 def test_date_elapsed_does_not_turn_past_programs_into_open_results(self):
  s=self.turn(new_state(),'강서구 국악공연');rows=visible_activities(s);self.assertTrue(rows)
  self.assertTrue(all(r.get('availability_status') not in {'open','walk_in'} for r in rows))
 def test_ui_accept_back_refuse_rerun_and_reset(self):
  with patch('services.config.load_settings',return_value=Settings()):
   app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=15).run()
   app.button(key='example_0').click().run();app.button(key='choose_region').click().run()
   row=visible_activities(app.session_state['dialog'])[0]
   app.chat_input(key='chat').set_value('좋아요').run();self.assertEqual(app.session_state['dialog']['selected_id'],row['id'])
   self.assertTrue(any('문의 전화' in m.value for m in app.markdown));app.run()
   self.assertEqual(app.session_state['dialog']['selected_id'],row['id'])
   app.button(key='detail_back').click().run();app.button(key='reject_recommendations').click().run()
   self.assertFalse(visible_activities(app.session_state['dialog']));self.assertTrue(app.button(key='request_adjacent'))
   app.chat_input(key='chat').set_value('대화 초기화').run();self.assertFalse(app.session_state['dialog']['conditions']);self.assertFalse(app.session_state['turns']);self.assertFalse(app.exception)

 def test_back_command_preserves_recommendations_without_external_completion(self):
  s=self.turn(new_state(),'강서구 수영 프로그램');ids=[r['id'] for r in visible_activities(s)]
  s=self.turn(s,'좋아요');s=self.turn(s,'뒤로');self.assertFalse(s['detail_focus']);self.assertEqual([r['id'] for r in visible_activities(s)],ids)
 def test_general_idea_refusal_does_not_repeat_same_ideas(self):
  s=self.turn(new_state(),'강서구에서 다른 운동 추천해줘');old={x['id'] for x in s['ideas']};self.assertTrue(old)
  s=self.turn(s,'다른 거 추천해 줘');self.assertFalse(old&{x['id'] for x in s['ideas']})
 def test_explicit_reset_cannot_be_overridden_by_provider(self):
  from services.ai import empty_extraction
  s=self.turn(new_state(),'강서구 수영 프로그램')
  with patch('services.dialogue.extract_conditions',return_value=empty_extraction('other')) as provider:
   s=discovery_turn(s,'대화 초기화',self.rows,Settings(gemini_api_key='mock'),as_of=DAY)[0]
   provider.assert_not_called();self.assertEqual(s['code'],'start');self.assertFalse(s['history']);self.assertFalse(s['conditions'])
 def test_short_refinement_response_asks_only_selected_condition(self):
  s=self.turn(new_state(),'강서구 수영 프로그램');s=self.turn(s,'마음에 안 들어');s=self.turn(s,'시간')
  self.assertEqual(s['pending'],'time_slot');self.assertEqual(s['conditions']['region'],'강서구')
  s=self.turn(s,'오전');self.assertEqual(s['conditions']['time_slot'],'오전');self.assertFalse(visible_activities(s))

 def test_schedule_ranges_are_not_interpreted_as_markdown_deletion(self):
  with patch('services.config.load_settings',return_value=Settings()):
   app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=15).run()
   app.chat_input(key='chat').set_value('서울 강서구 슬로우 러닝 프로그램').run()
   schedule=next(x.value for x in app.chat_message[-1].markdown if x.value.startswith('**시간**'))
   self.assertIn('\\~',schedule);self.assertNotIn('~',schedule.replace('\\~',''))
 def test_return_after_condition_change_never_restores_stale_conditions(self):
  s=self.turn(new_state(),'강서구 수영 프로그램');s=self.turn(s,'좋아요');self.assertIn('recommendation_context',s)
  s=self.turn(s,'오후가 좋아요');current=deepcopy(s['conditions']);s=return_to_recommendations(s)
  self.assertEqual(s['conditions'],current);self.assertEqual(s['conditions']['time_slot'],'오후')
  with patch('services.config.load_settings',return_value=Settings()):
   app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=15).run()
   for text in ('서울 강서구 수영 프로그램','좋아요','오후가 좋아요'):
    app.chat_input(key='chat').set_value(text).run()
   before=deepcopy(app.session_state['dialog']['conditions'])
   app.button(key='reopen_recommendations').click().run()
   self.assertEqual(app.session_state['dialog']['conditions'],before);self.assertFalse(app.exception)
 def test_acknowledgement_during_application_keeps_current_step(self):
  s=self.turn(new_state(),'강서구 수영 프로그램');s=self.turn(s,'좋아요');s=self.turn(s,'신청 방법 알려줘')
  before=deepcopy(s['application_helper']);s=self.turn(s,'네')
  self.assertTrue(s['helper_focus']);self.assertEqual(s['application_helper'],before);self.assertFalse(s['detail_focus'])

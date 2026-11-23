from copy import deepcopy
from datetime import date
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from services.activities import load_activities
from services.config import Settings
from services.dialogue import new_state
from services.discovery import discovery_turn,visible_activities
from services.guided_flow import choose_interest,open_picker,choose_city,choose_district,choose_area,dong_options,verified_dong
from services.ai import empty_extraction,AIError
from services.recommendations import recommend

ROOT=Path(__file__).resolve().parents[1]
DAY=date(2026,11,23)
class GuidedFlowTest(TestCase):
 def setUp(self):self.rows=load_activities();self.settings=Settings()
 def turn(self,s,text):return discovery_turn(s,text,self.rows,self.settings,as_of=DAY)[0]
 def app(self):return AppTest.from_file(str(ROOT/'app.py'),default_timeout=15).run()
 def test_button_interest_and_city_district_dong_share_conditions(self):
  s=choose_interest(new_state(),'문화',self.rows,self.settings);self.assertEqual(s['pending'],'region')
  s=open_picker(s,'region_city');s=choose_city(s,'서울');s=choose_district(s,'강서구',self.rows,self.settings)
  self.assertEqual(s['picker']['stage'],'region_dong')
  s=choose_area(s,'서울','강서구','화곡동',self.rows,self.settings)
  self.assertEqual(s['conditions']['region'],'강서구');self.assertEqual(s['conditions']['neighbourhood'],'화곡동')
  rows=visible_activities(s);self.assertTrue(rows);self.assertTrue(all(verified_dong(r)=='화곡동' for r in rows))
 def test_missing_region_has_no_other_regions_results(self):
  s=choose_interest(new_state(),'운동',self.rows,self.settings);s=open_picker(s,'region_city');s=choose_city(s,'창원')
  s=choose_district(s,'성산구',self.rows,self.settings)
  self.assertEqual(s['code'],'unsupported_region');self.assertFalse(visible_activities(s));self.assertEqual(s['conditions']['region'],'창원 성산구')
 def test_busans_gangseo_is_not_seoul_gangseo(self):
  s=choose_interest(new_state(),'운동',self.rows,self.settings);s=open_picker(s,'region_city');s=choose_city(s,'부산');s=choose_district(s,'강서구',self.rows,self.settings)
  self.assertEqual(s['conditions']['region'],'부산 강서구');self.assertFalse(visible_activities(s))
 def test_dong_options_require_literal_address_evidence(self):
  options=dong_options(self.rows,'서울','강서구');self.assertIn('화곡동',options)
  garden=next(r for r in self.rows if r['id']=='botanic-mini-garden-202611')
  self.assertIsNone(verified_dong(garden)) # A road name ending in 동로 is not a verified dong.
  self.assertFalse(recommend([garden],{'region':'강서구','neighbourhood':'마곡동'},as_of=DAY)['results'])
 def test_free_text_continues_draft_city_without_guessing_seoul(self):
  s=open_picker(new_state(),'region_city');s=choose_city(s,'부산');s=self.turn(s,'강서구요')
  self.assertEqual(s['conditions']['region'],'부산 강서구');self.assertFalse(visible_activities(s));self.assertNotIn('picker',s)
 def test_region_changes_clear_old_dong_but_keep_time_budget(self):
  s=self.turn(new_state(),'강서구 화곡동 무료 문화 행사');s=self.turn(s,'오후가 좋아요')
  s=self.turn(s,'창원 성산구요');self.assertNotIn('neighbourhood',s['conditions']);self.assertEqual(s['conditions']['time_slot'],'오후');self.assertEqual(s['conditions']['budget_amount'],0)
 def test_interest_change_preserves_region_time_budget_and_company(self):
  s=self.turn(new_state(),'강서구에서 무료로 함께 할 수 있는 활동');s=self.turn(s,'오후가 좋아요')
  s=choose_interest(s,'운동',self.rows,self.settings)
  for key,value in [('region','강서구'),('time_slot','오후'),('budget_amount',0),('companionship','함께')]:self.assertEqual(s['conditions'][key],value)
 def test_given_region_is_not_asked_again_and_all_five_interests_work(self):
  s=self.turn(new_state(),'강서구에서 찾아줘')
  for label in ('운동','취미','문화','배움','사람 만나기'):
   result=choose_interest(s,label,self.rows,self.settings);self.assertNotEqual(result['pending'],'region');self.assertLessEqual(len(visible_activities(result)),3)
 def test_gemini_failure_then_buttons_continue_without_disguising_failure(self):
  with patch('services.dialogue.extract_conditions',side_effect=AIError(code='timeout')):
   s=discovery_turn(new_state(),'강서구 화곡동 문화 행사',self.rows,Settings(gemini_api_key='mock'),as_of=DAY)[0]
  self.assertEqual(s['mode'],'fallback');self.assertEqual(s['conditions']['neighbourhood'],'화곡동')
  s=choose_interest(s,'문화',self.rows,self.settings);self.assertEqual(s['conditions']['region'],'강서구')
 def test_model_cannot_invent_dong(self):
  payload=empty_extraction();payload['conditions']['neighbourhood']='화곡동';payload['update_fields']=['neighbourhood']
  s=discovery_turn(new_state(),'문화 활동',self.rows,Settings(),as_of=DAY,extraction=payload)[0]
  self.assertNotIn('neighbourhood',s['conditions'])
 def test_buttons_only_reach_participation_then_back_reset(self):
  with patch('services.config.load_settings',return_value=Settings()):
   app=self.app();app.button(key='start_interest_0').click().run();app.button(key='counsel_suggest').click().run();app.button(key='idea_walking').click().run();app.button(key='choose_region').click().run()
   next(b for b in app.button if b.label=='서울특별시 →').click().run();next(b for b in app.button if b.label=='강서구 →').click().run();app.button(key='region_all').click().run();app.button(key='region_confirm').click().run()
   row=visible_activities(app.session_state['dialog'])[0];app.button(key='detail_'+row['id']).click().run();app.button(key='apply_'+row['id']).click().run()
   self.assertTrue(app.session_state['dialog']['helper_focus']);self.assertEqual(app.session_state['dialog']['selected_id'],row['id'])
   self.assertTrue(any('신청 방식' in m.value for m in app.markdown))
   app.button(key='header_menu').click().run();app.button(key='nav_previous').click().run();self.assertEqual(app.session_state['dialog']['selected_id'],row['id']);self.assertFalse(app.session_state['dialog']['helper_focus'])
   app.button(key='header_menu').click().run();app.button(key='nav_reset').click().run();app.button(key='confirm_reset_yes').click().run();self.assertFalse(app.session_state['dialog']['conditions']);self.assertFalse(app.session_state['navigation_history']);self.assertFalse(app.exception)
 def test_font_preferences_do_not_change_dialogue_and_survive_reset(self):
  with patch('services.config.load_settings',return_value=Settings()):
   app=self.app();app.button(key='start_interest_0').click().run();before=deepcopy(app.session_state['dialog'])
   app.button(key='font_settings').click().run();app.button(key='font_choice_1').click().run();self.assertEqual(app.session_state['font_level'],1);self.assertEqual(app.session_state['dialog'],before)
   app.button(key='font_settings').click().run();app.button(key='font_choice_2').click().run();app.button(key='font_settings').click().run();self.assertIn('✓',app.button(key='font_choice_2').label);app.button(key='font_close').click().run()
   app.button(key='header_menu').click().run();app.button(key='nav_reset').click().run();self.assertEqual(app.session_state['font_level'],2)
 def test_previous_in_picker_restores_stage_and_selection(self):
  with patch('services.config.load_settings',return_value=Settings()):
   app=self.app();app.chat_input(key='chat').set_value('부산 해운대구 우동 수영').run()
   before=deepcopy(app.session_state['dialog']['conditions'])
   app.button(key='region_change').click().run();next(b for b in app.button if b.label=='서울특별시 →').click().run()
   app.button(key='region_close').click().run();self.assertFalse(app.session_state['region_open'])
   self.assertEqual(app.session_state['dialog']['conditions'],before);self.assertFalse(app.exception)
 def test_condition_reselection_does_not_erase_other_conditions(self):
  with patch('services.config.load_settings',return_value=Settings()):
   app=self.app();app.chat_input(key='chat').set_value('서울 강서구 오후 무료 문화 활동').run();app.button(key='header_menu').click().run();app.button(key='nav_reselect').click().run();app.button(key='edit_activity').click().run();app.button(key='pick_interest_0').click().run()
   self.assertEqual(app.session_state['dialog']['conditions']['region'],'서울 강서구');self.assertEqual(app.session_state['dialog']['conditions']['time_slot'],'오후');self.assertEqual(app.session_state['dialog']['conditions']['budget_amount'],0)
 def test_free_text_skip_dong_uses_already_chosen_city_and_district(self):
  s=choose_interest(new_state(),'운동',self.rows,self.settings);s=open_picker(s,'region_city');s=choose_city(s,'서울');s=choose_district(s,'강서구',self.rows,self.settings)
  s=self.turn(s,'상관없어요');self.assertEqual(s['conditions']['region'],'강서구');self.assertNotEqual(s['pending'],'region');self.assertNotIn('neighbourhood',s['conditions'])
 def test_condition_input_during_city_choice_keeps_city_question(self):
  s=self.turn(new_state(),'강서구 운동');s=open_picker(s,'region_city');s=choose_city(s,'부산');s=self.turn(s,'가능하시면 오후가 좋아요')
  self.assertEqual(s['picker']['city'],'부산');self.assertEqual(s['pending'],'region');self.assertFalse(visible_activities(s))
  s=choose_district(s,'강서구',self.rows,self.settings);self.assertEqual(s['conditions']['region'],'부산 강서구');self.assertEqual(s['conditions']['time_slot'],'오후');self.assertFalse(visible_activities(s))
 def test_direct_city_without_district_is_honest_when_unsupported(self):
  known=self.turn(new_state(),'서울시에서 운동');self.assertEqual(known['conditions']['region'],'서울');self.assertNotEqual(known['code'],'unsupported_region')
  for text in ('부산에서 운동','수원시에서 운동'):
   s=self.turn(new_state(),text);self.assertEqual(s['code'],'unsupported_region');self.assertFalse(visible_activities(s))

 def test_numbered_dong_is_not_silently_ignored_or_replaced_by_whole_district(self):
  s=choose_interest(new_state(),'문화',self.rows,self.settings);s=open_picker(s,'region_city');s=choose_city(s,'서울');s=choose_district(s,'강서구',self.rows,self.settings)
  s=self.turn(s,'등촌1동에서 찾아줘');self.assertEqual(s['conditions']['region'],'강서구');self.assertEqual(s['conditions']['neighbourhood'],'등촌1동');self.assertFalse(visible_activities(s))
  self.assertEqual(verified_dong({'address':'서울 강서구 등촌1동 12'}),'등촌1동')

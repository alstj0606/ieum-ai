"""User-first P0, factual read model, session safety and preserved institution access."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import TestCase
from unittest.mock import Mock,patch
from streamlit.testing.v1 import AppTest
from services.ai import empty_extraction,AIError,validate_extraction
from services.activities import load_activities,validate_activities
from services.activity_catalog import catalog_entry
from services.config import Settings
from services.dialogue import new_state,basic_extract,application_guide
from services.discovery import discovery_turn,visible_activities,select_activity,institution_for_selection,safe_input
from services.recommendations import recommend

ROOT=Path(__file__).resolve().parents[1];DAY=date(2026,11,13)
class DiscoveryTest(TestCase):
 def setUp(self):self.rows=load_activities()
 def turn(self,s,text,**kw):return discovery_turn(s,text,self.rows,Settings(),as_of=DAY,**kw)[0]
 def test_swim_region_then_honest_alternative_no_repeated_region(self):
  s=self.turn(new_state(),'수영하고 싶어요');self.assertEqual(s['pending'],'region')
  s=self.turn(s,'서울 강서구요');self.assertNotEqual(s['pending'],'region')
  self.assertFalse(s['results']);rows=visible_activities(s);self.assertLessEqual(len(rows),3)
  self.assertTrue(all(r['id'] in {x['id'] for x in self.rows} for r in rows))
  self.assertTrue(all(r['activity_type']!='수영' for r in rows));self.assertIn(rows[0]['match_label'],('유사 활동','다른 대안'))
 def test_slow_running_alias_and_closed_status(self):
  s=self.turn(new_state(),'서울 강서구 슬로우 러닝을 해보고 싶어요')
  self.assertEqual(s['conditions']['activity_type'],'슬로우조깅')
  rows=visible_activities(s);self.assertEqual(rows[0]['activity_type'],'슬로우조깅');self.assertEqual(rows[0]['availability_status'],'closed')
 def test_region_change_does_not_reuse_gangseo_as_changwon(self):
  s=self.turn(new_state(),'강서구 국악 공연');self.assertTrue(visible_activities(s))
  s=self.turn(s,'창원 성산구요');self.assertFalse(visible_activities(s));self.assertEqual(s['code'],'unsupported_region')
  self.assertIn('실시간 검색은 하지',s['message'])
 def test_general_learning_one_question_then_company_and_region(self):
  s=self.turn(new_state(),'뭔가 새로운 걸 배우고 싶어요');self.assertEqual(s['pending'],'activity_type')
  self.assertEqual(s['history'][-1]['content'],s['message'])
  s=self.turn(s,'사람들과 같이하는 만들기요');self.assertEqual(s['pending'],'region');self.assertEqual(s['conditions']['companionship'],'함께')
  s=self.turn(s,'강서구요');self.assertNotEqual(s['pending'],'region')
 def test_conditions_change_clear_and_no_age_based_health_assumption(self):
  s=self.turn(new_state(),'65세 강서구 가벼운 운동');s=self.turn(s,'오후가 좋아요');s=self.turn(s,'무료로 찾아줘')
  self.assertEqual(s['conditions']['age'],65);self.assertEqual(s['conditions']['region'],'강서구')
  self.assertEqual(s['conditions']['time_slot'],'오후');self.assertEqual(s['conditions']['budget_amount'],0)
  self.assertNotIn('movement_caution',s['conditions'])
  s=self.turn(s,'시간은 상관없어요');self.assertNotIn('time_slot',s['conditions'])
 def test_health_detail_is_not_retained_or_sent_to_model(self):
  payload=empty_extraction();payload['conditions']['region']='강서구';payload['update_fields']=['region']
  client=Mock();client.models.generate_content.return_value=NS(text=json.dumps(payload),candidates=[NS(finish_reason='STOP')],prompt_feedback=None)
  raw='무릎이 불편해요. 강서구 무료 걷기요'
  s,safe=discovery_turn(new_state(),raw,self.rows,Settings(gemini_api_key='mock'),client=client,as_of=DAY)
  self.assertNotIn('무릎',safe);self.assertNotIn('무릎',json.dumps(s,ensure_ascii=False))
  self.assertNotIn('무릎',client.models.generate_content.call_args.kwargs['contents'])
  self.assertEqual(s['conditions']['movement_caution'],'부담 확인')
  s=self.turn(s,'신체 부담 조건 해제');self.assertNotIn('movement_caution',s['conditions'])
 def test_ai_cannot_invent_region_weekday_or_company(self):
  payload=empty_extraction();payload['conditions'].update(region='강서구',weekdays=['월'],companionship='함께')
  payload['update_fields']=['region','weekdays','companionship']
  client=Mock();client.models.generate_content.return_value=NS(text=json.dumps(payload),candidates=[NS(finish_reason='STOP')],prompt_feedback=None)
  s,_=discovery_turn(new_state(),'수영하고 싶어요',self.rows,Settings(gemini_api_key='mock'),client=client,as_of=DAY)
  self.assertEqual(s['pending'],'region');self.assertNotIn('region',s['conditions'])
  self.assertNotIn('weekdays',s['conditions']);self.assertNotIn('companionship',s['conditions'])
 def test_private_input_is_not_sent_or_saved(self):
  client=Mock();s,safe=discovery_turn(new_state(),'비밀번호: secret-canary',self.rows,Settings(gemini_api_key='mock'),client=client)
  client.models.generate_content.assert_not_called();self.assertNotIn('secret-canary',str(s)+safe)
  self.assertIn('개인정보',s['error'])
  self.assertFalse(safe_input('100000원 이하로',new_state())[2])
  self.assertNotIn('무릎',safe_input('130세 무릎이 불편해요',new_state())[0])
 def test_api_failure_is_not_claimed_as_success(self):
  client=Mock();client.models.generate_content.side_effect=TimeoutError('private-provider-body')
  s,_=discovery_turn(new_state(),'강서구 국악 공연',self.rows,Settings(gemini_api_key='mock'),client=client,as_of=DAY)
  self.assertEqual(s['mode'],'fallback');self.assertTrue(visible_activities(s));self.assertNotIn('private-provider-body',str(s))
 def test_catalog_keeps_original_zero_null_unknowns_and_current_status(self):
  originals=deepcopy(self.rows)
  for row in self.rows:
   common=catalog_entry(row,as_of=DAY)
   self.assertEqual(common['activity_id'],row['id']);self.assertEqual(common['source_checked_at'],row['verified_at'])
   self.assertEqual(common['price']['amount'],row['fee_amount']);self.assertIsNone(common['physical_intensity'])
   self.assertIsNone(common['beginner_friendly']);self.assertEqual(common['application_url'],row['official_url'])
  self.assertEqual(self.rows,originals)
  row=deepcopy(self.rows[4]);row['fee_amount']=None;self.assertIsNone(catalog_entry(row)['price']['amount'])
  row['fee_amount']=0;self.assertEqual(catalog_entry(row)['price']['amount'],0)
 def test_future_regions_and_weekdays_use_verified_attributes_only(self):
  row=deepcopy(self.rows[4]);row.update(id='fixture-changwon-not-production',region='경남 창원시 성산구',companionship='함께')
  row['schedule']['weekdays']=['토'];validate_activities([row])
  result=recommend([row],{'region':'창원 성산구','weekdays':['토']},as_of=DAY);self.assertTrue(result['results'])
  self.assertFalse(recommend([row],{'region':'창원 성산구','weekdays':['월']},as_of=DAY)['results'])
  row['schedule'].pop('weekdays');row['schedule']['text']='운영 요일 확인 필요';result=recommend([row],{'region':'창원 성산구','weekdays':['토']},as_of=DAY)
  self.assertFalse(result['results']);self.assertTrue(result['references']);self.assertIn('요일',result['references'][0]['condition_notes'][0])
 def test_unknown_weekday_stays_reference_through_card_and_application(self):
  s=self.turn(new_state(),'강서구 토요일 숲체험')
  self.assertFalse(s['results']);rows=visible_activities(s);self.assertTrue(rows)
  self.assertTrue(rows[0]['requires_confirmation'])
  chosen=select_activity(s,rows[0]['id'],self.rows,Settings(),as_of=DAY)
  guided=application_guide(chosen,self.rows,as_of=DAY)
  self.assertEqual(guided['application_helper']['mode'],'check')
  self.assertNotIn('다음 모집을 확인하는 안내',guided['message'])
 def test_operating_weekday_text_is_not_confused_with_closure(self):
  from services.activity_catalog import known_weekdays
  garden=next(r for r in self.rows if r['activity_type']=='가드닝')
  golf=next(r for r in self.rows if r['activity_type']=='파크골프')
  self.assertEqual(known_weekdays(garden),['목']);self.assertIsNone(known_weekdays(golf))
  self.assertFalse(recommend([garden],{'region':'강서구','weekdays':['토']},as_of=DAY)['results'])
  self.assertTrue(recommend([garden],{'region':'강서구','weekdays':['목']},as_of=DAY)['results'])
 def test_schema_new_slots_rejects_facts_and_invalid_weekday(self):
  payload=empty_extraction();payload['conditions']['weekdays']=['목'];payload['update_fields']=['weekdays'];validate_extraction(payload)
  payload['conditions']['weekdays']=['내일'];self.assertRaises(AIError,validate_extraction,payload)
  payload=empty_extraction();payload['conditions']['phone']='invented';self.assertRaises(AIError,validate_extraction,payload)
 def test_card_selection_and_application_revalidate_official_id(self):
  s=self.turn(new_state(),'강서구 걷기 프로그램');rows=visible_activities(s)
  chosen=select_activity(s,rows[0]['id'],self.rows,Settings(),as_of=DAY)
  self.assertEqual(chosen['selected_id'],rows[0]['id'])
  guided=application_guide(chosen,self.rows,as_of=DAY);self.assertTrue(guided.get('application_helper'))
  self.assertRaises(ValueError,select_activity,s,'invented',self.rows,Settings())
 def test_institution_route_requires_selected_verified_program(self):
  self.assertIsNone(institution_for_selection({},self.rows))
  row=deepcopy(self.rows[0]);row['institution_id']='seongsan_senior';rows=[row]
  self.assertIsNone(institution_for_selection({'selected_id':row['id']},rows))
  self.assertEqual(institution_for_selection({'selected_id':row['id'],'references':[row]},rows),'seongsan_senior')
 def test_default_app_landing_examples_voice_status_and_conversation(self):
  with patch('services.config.load_settings',return_value=Settings()):
   app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=15).run()
   self.assertFalse(app.exception);self.assertEqual(app.header[0].value,'오늘은 무엇을 해보고 싶으세요?')
   self.assertNotIn('inst_start',[b.key for b in app.button]);self.assertTrue(app.button(key='voice_unavailable').disabled)
   app.button(key='example_0').click().run();self.assertEqual(app.session_state['dialog']['pending'],'region')
   app.button(key='choose_region').click().run();self.assertFalse(app.exception)
   ids=[r['id'] for r in visible_activities(app.session_state['dialog'])]
   self.assertTrue(ids);app.button(key='detail_'+ids[0]).click().run();self.assertEqual(app.session_state['dialog']['selected_id'],ids[0])
   app.button(key='apply_'+ids[0]).click().run();self.assertTrue(app.session_state['dialog']['application_helper'])
   app.chat_input(key='chat').set_value('창원 성산구요').run();self.assertFalse(visible_activities(app.session_state['dialog']))
   self.assertFalse(app.exception)
 def test_health_text_does_not_remain_in_ui_session(self):
  with patch('services.config.load_settings',return_value=Settings()):
   app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=15).run()
   app.chat_input(key='chat').set_value('무릎이 불편해요. 강서구 걷기요').run()
   self.assertFalse(app.exception);self.assertNotIn('무릎',str(app.session_state))
   self.assertEqual(app.session_state['dialog']['conditions']['movement_caution'],'부담 확인')
 def test_contact_is_taken_from_verified_guide_not_generated(self):
  from services.application_helper import load_guides
  row=next(r for r in self.rows if r['activity_type']=='파크골프');guide=load_guides()[row['id']]
  entry=catalog_entry(row);self.assertEqual(entry['contact_phone'],guide['contact']['phone'])
  self.assertEqual(entry['contact_checked_at'],guide['verified_at']);self.assertEqual(entry['contact_source'],guide['source_url'])
 def test_catalog_load_error_keeps_default_app_usable_without_fake_results(self):
  with patch('services.config.load_settings',return_value=Settings()),patch('services.activities.load_activities',side_effect=ValueError('invalid-data')):
   app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=15).run()
   self.assertFalse(app.exception);self.assertTrue(app.error)
   self.assertTrue(any('0건' in c.value for c in app.caption))
   app.button(key='example_0').click().run();self.assertFalse(app.exception)
   self.assertFalse(visible_activities(app.session_state['dialog']))
 def test_region_question_uses_dataset_coverage_without_fabricating_records(self):
  row=deepcopy(self.rows[4]);row['region']='경남 창원시 성산구';row['id']='future-region-test-fixture'
  s,_=discovery_turn(new_state(),'수영하고 싶어요',[row],Settings(),as_of=DAY)
  self.assertEqual(s['pending'],'region');self.assertIn('창원',s['message']);self.assertNotIn('강서구',s['message'])
 def test_no_institution_entry_without_official_program_selection(self):
  with patch('services.config.load_settings',return_value=Settings()):
   app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=15)
   app.session_state['service_mode']='seongsan';app.run()
   self.assertTrue(app.header);self.assertNotIn('inst_start',[b.key for b in app.button]);self.assertFalse(app.exception)

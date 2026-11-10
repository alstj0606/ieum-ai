"""Explicit session profiles and source-grounded ranking, without live credentials."""
from copy import deepcopy
from datetime import date
from unittest import TestCase
from unittest.mock import Mock
from services.activities import load_activities
from services.config import Settings
from services.dialogue import new_state,handle_turn,choose_alternative
from services.personalization import profile_conditions,hard_conditions
from services.recommendation_pipeline import score_program

DAY=date(2026,11,10)
class PersonalizationTest(TestCase):
 def setUp(self):self.rows=load_activities()
 def turn(self,s,text):return handle_turn(s,text,self.rows,Settings(),as_of=DAY)
 def profile(self):return self.turn(new_state(),'65세인데 집에만 있어서 가볍게 운동하고 싶어요. 강서구에 살아요.')
 def test_explicit_profile_without_health_inference(self):
  s=self.profile();c=s['conditions']
  self.assertEqual((c['age'],c['region'],c['effort_preference'],c['purpose']),(65,'강서구','가볍게','운동'))
  self.assertEqual(c['residence'],'서울 강서구')
  self.assertFalse({'health','disability','gender','mobility'} & c.keys())
  self.assertNotIn('residence',self.turn(new_state(),'65세 강서구에서 가볍게 운동하고 싶어요')['conditions'])
 def test_accumulate_soft_time_hard_budget_and_clear(self):
  s=self.turn(self.profile(),'오후가 좋아요');s=self.turn(s,'무료로 찾아줘')
  self.assertEqual(s['conditions']['region'],'강서구');self.assertEqual(s['conditions']['age'],65)
  self.assertEqual(s['condition_modes'],{'time_slot':'preferred','budget_amount':'required'})
  c=hard_conditions(profile_conditions(s));self.assertNotIn('time_slot',c);self.assertEqual(c['budget_amount'],0)
  s=self.turn(s,'시간은 상관없어요');self.assertNotIn('time_slot',s['conditions']);self.assertNotIn('time_slot',s['condition_modes'])
 def test_change_activity_preserves_profile_excludes_rejected(self):
  s=self.turn(self.profile(),'오후가 좋아요');s=self.turn(s,'무료로 찾아줘');s=self.turn(s,'수영 말고 다른 운동은요?')
  self.assertNotIn('activity_type',s['conditions']);self.assertEqual(s['conditions']['purpose'],'운동')
  self.assertEqual(s['conditions']['time_slot'],'오후');self.assertEqual(s['conditions']['budget_amount'],0)
  self.assertIn('수영',s['excluded_types']);self.assertTrue(s['ideas']);self.assertNotIn('수영',[x['activity_type'] for x in s['ideas']])
  s=self.turn(s,'강서구 수영 프로그램 찾아줘');self.assertNotIn('수영',s['excluded_types'])
 def test_reset_clears_session_profile(self):
  s=self.turn(self.profile(),'처음부터 다시');self.assertEqual(s['conditions'],{});self.assertEqual(s['condition_modes'],{});self.assertEqual(s['excluded_types'],[])
 def test_one_optional_question_then_region_then_recommend(self):
  s=self.turn(new_state(),'운동 추천해 줘');self.assertEqual(s['pending'],'effort_preference');self.assertEqual(s['message'].count('?'),1)
  s=self.turn(s,'가볍게요');self.assertEqual(s['pending'],'region')
  s=self.turn(s,'강서구요');self.assertIsNone(s['pending']);self.assertTrue(s['results'] or s['references'])
 def test_skip_preference_does_not_repeat_it(self):
  s=self.turn(new_state(),'운동 추천해 줘');s=self.turn(s,'상관없어요');self.assertEqual(s['pending'],'region')
  s=self.turn(s,'강서구요');self.assertNotEqual(s['pending'],'effort_preference')
 def test_source_only_preference_points_and_intensity_caution(self):
  row=self.rows[0];c={'region':'강서구','activity_type':row['activity_type']}
  base=score_program(row,c,as_of=DAY)
  changed=score_program(row,dict(c,age=65,effort_preference='가볍게',mobility='이동 적게'),as_of=DAY)
  self.assertEqual(base['score'],changed['score']);self.assertIn('확인이 필요',changed['reason'])
  slot=row['schedule']['time_slots'][0] if row['schedule']['time_slots'] else '오후'
  preferred=dict(c,time_slot=slot,_modes={'time_slot':'preferred'})
  known=deepcopy(row);known['schedule']['time_slots']=[slot]
  unknown=deepcopy(row);unknown['schedule']['time_slots']=[]
  self.assertGreater(score_program(known,preferred,as_of=DAY)['score'],score_program(unknown,preferred,as_of=DAY)['score'])
 def test_walking_first_and_closed_reference(self):
  s=self.turn(new_state(),'강서구 걷기 프로그램 찾아줘');self.assertEqual(s['alternatives'][0]['activity_type'],'슬로우조깅')
  self.assertEqual(s['alternatives'][0]['match_label'],'유사 활동');self.assertEqual(s['alternatives'][1]['match_label'],'다른 대안')
  selected=choose_alternative(s,s['alternatives'][0]['activity_type'],self.rows,Settings(),as_of=DAY)
  self.assertEqual(selected['code'],'closed');self.assertFalse(selected['results']);self.assertTrue(selected['references'])
 def test_expansion_requires_consent_and_cannot_reuse_local(self):
  s=self.turn(new_state(),'강서구 걷기 프로그램 찾아줘');s=self.turn(s,'인접 지역도 찾아줘')
  self.assertEqual(s['pending'],'expand_region');self.assertNotEqual(s['flow'],'adjacent')
  denied=self.turn(s,'아니요');self.assertFalse(denied['expanded'])
  yes=self.turn(s,'네');self.assertEqual(yes['flow'],'adjacent');self.assertFalse(yes['results']);self.assertFalse(yes['references']);self.assertIn('현재 확인된 인접 지역 프로그램 자료가 없습니다',yes['message'])
 def test_failed_gemini_keeps_profile_and_honest_fallback(self):
  client=Mock();client.models.generate_content.side_effect=TimeoutError('private-provider-canary')
  s=handle_turn(new_state(),'65세 강서구 가벼운 걷기 프로그램 찾아줘',self.rows,Settings(gemini_api_key='mock'),client=client,as_of=DAY)
  self.assertEqual(s['mode'],'fallback');self.assertEqual(s['diagnostic']['code'],'timeout');self.assertEqual(s['conditions']['age'],65)
  self.assertEqual(s['alternatives'][0]['activity_type'],'슬로우조깅');self.assertNotIn('private-provider-canary',str(s))
 def test_soft_budget_zero_unknown_and_required_time(self):
  s=self.turn(self.profile(),'무료였으면 좋겠어요');self.assertEqual(s['condition_modes']['budget_amount'],'preferred')
  c=profile_conditions(s);self.assertNotIn('budget_amount',hard_conditions(c))
  free=deepcopy(self.rows[0]);free['fee_amount']=0
  unknown=deepcopy(free);unknown['fee_amount']=None
  f=score_program(free,c,as_of=DAY);u=score_program(unknown,c,as_of=DAY)
  self.assertEqual(f['score_parts']['budget_preference'],4);self.assertEqual(u['score_parts']['budget_preference'],0)
  self.assertIn('무료로 확인',f['reason']);self.assertNotIn('무료로 확인',u['reason'])
  s=self.turn(s,'오후로 찾아줘');self.assertEqual(s['condition_modes']['time_slot'],'required');self.assertEqual(hard_conditions(profile_conditions(s))['time_slot'],'오후')
 def test_gemini_structured_profile_reuses_validation(self):
  import json
  from types import SimpleNamespace as NS
  from services.ai import empty_extraction
  data=empty_extraction('recommend_activity');data['conditions'].update(age=65,region='강서구',category='체육',effort_preference='가볍게',purpose='운동')
  data['update_fields']=['age','region','category','effort_preference','purpose']
  client=Mock();client.models.generate_content.return_value=NS(text=json.dumps(data),prompt_feedback=None,candidates=[NS(finish_reason='STOP')])
  s=handle_turn(new_state(),'65세이고 강서구에서 가볍게 운동하고 싶어요',self.rows,Settings(gemini_api_key='mock'),client=client,as_of=DAY)
  self.assertEqual(s['mode'],'gemini');self.assertIsNone(s['diagnostic']);self.assertEqual(s['conditions']['age'],65);self.assertNotIn('residence',s['conditions'])
  self.assertTrue(s['results'] or s['references'])

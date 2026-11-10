"""Recommendation/facility/program routing and conservative personalization; no live API."""
from copy import deepcopy
from datetime import date
from types import SimpleNamespace as NS
from unittest import TestCase
from unittest.mock import Mock
import json

from services.activities import load_activities
from services.config import Settings
from services.dialogue import new_state, handle_turn, choose_idea
from services.ai import empty_extraction

DAY=date(2026,11,9)

class ActivityGuidanceTest(TestCase):
    def setUp(self):self.rows=load_activities()
    def turn(self,state,text,**kwargs):return handle_turn(state,text,self.rows,Settings(),as_of=DAY,**kwargs)

    def test_elderly_exercise_returns_general_options_without_assumed_age_or_health(self):
        state=self.turn(new_state(),'노인이 할 수 있는 운동 추천해 줘')
        self.assertEqual(self.turn(new_state(),'노인이 할 수 있는 운동')['code'],'ideas')
        self.assertEqual(state['code'],'ideas')
        self.assertEqual(state['routing_intent'],'recommend_activity')
        self.assertEqual(len(state['ideas']),3)
        self.assertFalse(state['results'])
        self.assertNotIn('age',state['conditions'])
        self.assertIn('실제 모집 프로그램은 아니에요',state['message'])
        self.assertEqual(state['message'].count('?'),1)
        for idea in state['ideas']:
            self.assertNotIn('fee_amount',idea)
            self.assertNotIn('official_url',idea)

    def test_nearby_swimming_pool_asks_region_then_shows_only_sourced_facilities(self):
        state=self.turn(new_state(),'근처 수영장 찾아줘')
        self.assertEqual(state['routing_intent'],'find_facility')
        self.assertEqual(state['pending'],'region')
        self.assertNotIn('region',state['conditions'])
        state=self.turn(state,'강서구요')
        self.assertEqual(state['code'],'facilities')
        self.assertTrue(state['facilities'])
        self.assertFalse(state['results'])
        for facility in state['facilities']:
            matches=[row for row in self.rows if row['facility_name']==facility['name']]
            self.assertTrue(matches)
            self.assertIn(facility['source_url'],[row['source_url'] for row in matches])
            self.assertIn('현재 시설 운영',facility['note'])
        self.assertIn('거리순으로 검색한 결과는 아니',state['message'])

    def test_specific_swimming_no_result_keeps_requested_type_and_offers_next_actions(self):
        state=self.turn(new_state(),'강서구에서 수영 배우고 싶어')
        self.assertEqual(state['code'],'no_match')
        self.assertEqual(state['conditions']['activity_type'],'수영')
        self.assertTrue(state['ideas'] or state['alternatives'])
        self.assertFalse(state['facilities'])
        before=state['message']
        state=self.turn(state,'같은 조건으로 다시 찾아주세요')
        self.assertNotEqual(state['message'],before)
        self.assertEqual(state['conditions']['activity_type'],'수영')
        self.assertIn('시간 조건을 풀어',state['message'])

    def test_other_exercise_resets_activity_filters_but_keeps_personal_preferences(self):
        state=self.turn(new_state(),'70세 강서구 오전 무료 운동 추천해 줘')
        initial={x['id'] for x in state['ideas']}
        state['conditions'].update(activity_type='수영',tags=['물'],purpose='배우기',beginner=True)
        state=self.turn(state,'다른 운동도 추천해 줘')
        self.assertNotEqual(initial,{x['id'] for x in state['ideas']})
        for key in ('activity_type','tags','purpose','beginner'):self.assertNotIn(key,state['conditions'])
        self.assertEqual(state['conditions']['age'],70)
        self.assertEqual(state['conditions']['time_slot'],'오전')
        self.assertEqual(state['conditions']['budget_amount'],0)
        self.assertEqual(state['conditions']['region'],'강서구')

    def test_morning_followup_and_condition_change_stay_in_recommendation_flow(self):
        state=self.turn(new_state(),'노인이 할 수 있는 운동 추천해 줘')
        state=self.turn(state,'오전에 할 수 있는 활동은?')
        self.assertEqual(state['conditions']['time_slot'],'오전')
        self.assertEqual(state['code'],'ideas')
        state=self.turn(state,'오전 말고 오후로 찾아줘')
        self.assertEqual(state['conditions']['time_slot'],'오후')
        self.assertEqual(state['routing_intent'],'change_condition')
        self.assertEqual(state['code'],'ideas')

    def test_choice_is_from_current_options_and_retains_budget_time_region(self):
        state=self.turn(new_state(),'강서구 오전 무료 운동 추천해 줘')
        before=deepcopy(state)
        choice=choose_idea(state,'walking',self.rows,Settings(),as_of=DAY)
        self.assertEqual(state,before)
        self.assertEqual(choice['conditions']['activity_type'],'걷기')
        self.assertEqual(choice['conditions']['time_slot'],'오전')
        self.assertEqual(choice['conditions']['budget_amount'],0)
        with self.assertRaises(ValueError):choose_idea(state,'invented',self.rows,Settings(),as_of=DAY)
        state=self.turn(new_state(),'운동 추천해 줘')
        state=choose_idea(state,'water',self.rows,Settings(),as_of=DAY)
        self.assertEqual(state['pending'],'region')
        self.assertEqual(state['conditions']['activity_type'],'아쿠아로빅')

    def test_explicit_interest_and_mobility_are_respected_without_claiming_distance(self):
        state=self.turn(new_state(),'75살 그림 취미 추천해줘. 이동이 어려워서 가까운 곳이면 좋겠어')
        self.assertEqual(state['conditions']['age'],75)
        self.assertIn('그림',state['conditions']['tags'])
        self.assertTrue(state['ideas'])
        self.assertTrue(all(x['near_home'] for x in state['ideas']))
        self.assertIn('거리',state['message'])
        self.assertTrue(any(x['activity_type']=='미술' for x in state['ideas']))

    def test_unsupported_region_is_honest_and_can_be_changed_explicitly(self):
        state=self.turn(new_state(),'마포구에서 수영 배우고 싶어')
        self.assertEqual(state['code'],'unsupported_region')
        self.assertEqual(state['conditions']['region'],'마포구')
        self.assertIn('실시간 검색한 것은 아니',state['message'])
        self.assertFalse(state['results'])
        state=self.turn(state,'서울 강서구요')
        self.assertEqual(state['conditions']['region'],'강서구')
        self.assertEqual(state['code'],'no_match')

    def test_gemini_failure_still_recommends_and_keeps_safe_failure_notice(self):
        client=Mock();client.models.generate_content.side_effect=TimeoutError('private-provider-error')
        state=handle_turn(new_state(),'노인이 할 수 있는 운동 추천해 줘',self.rows,Settings(gemini_api_key='mock'),client=client,as_of=DAY)
        self.assertEqual(state['mode'],'fallback')
        self.assertEqual(state['diagnostic']['code'],'timeout')
        self.assertEqual(state['code'],'ideas')
        self.assertTrue(state['ideas'])
        self.assertNotIn('private-provider-error',json.dumps(state))
        state=self.turn(state,'오전이 좋아요')
        self.assertEqual(state['conditions']['time_slot'],'오전')
        self.assertEqual(state['code'],'ideas')

    def test_gemini_intent_and_mobility_schema_work_but_invented_age_location_are_dropped(self):
        payload=empty_extraction('find_facility')
        payload['conditions'].update(region='강서구',age=65,activity_type='수영',mobility='도보')
        payload['update_fields']=['region','age','activity_type','mobility']
        client=Mock();client.models.generate_content.return_value=NS(prompt_feedback=None,candidates=[NS(finish_reason='STOP')],text=json.dumps(payload))
        state=handle_turn(new_state(),'근처 수영장 찾아줘. 어르신이고 도보로 가고 싶어',self.rows,Settings(gemini_api_key='mock'),client=client,as_of=DAY)
        self.assertEqual(state['mode'],'gemini')
        self.assertEqual(state['pending'],'region')
        self.assertNotIn('age',state['conditions'])
        self.assertNotIn('region',state['conditions'])
        self.assertEqual(state['conditions']['mobility'],'도보')

    def test_application_request_after_general_idea_does_not_book_or_invent_program(self):
        state=self.turn(new_state(),'운동 추천해줘')
        state=self.turn(state,'이거 어떻게 신청해?')
        self.assertEqual(state['code'],'choose')
        self.assertFalse(state['results'])
        self.assertIn('일반 활동 제안',state['message'])

    def test_relaxing_time_is_explicit_and_preserves_type_and_budget(self):
        state=self.turn(new_state(),'강서구 오후 무료 수영 배우고 싶어')
        state=self.turn(state,'시간은 상관없어요')
        self.assertNotIn('time_slot',state['conditions'])
        self.assertEqual(state['conditions']['activity_type'],'수영')
        self.assertEqual(state['conditions']['budget_amount'],0)

    def test_nearby_then_any_region_does_not_repeat_same_location_question(self):
        state=self.turn(new_state(),'근처 수영장 찾아줘')
        state=self.turn(state,'상관없어요')
        self.assertIsNone(state['pending'])
        self.assertEqual(state['code'],'unsupported_region')
        self.assertTrue(state['ideas'])
        self.assertIn('상관없다고',state['message'])

    def test_gemini_recommendation_intent_uses_explicit_profile_without_program_invention(self):
        payload=empty_extraction('recommend_activity')
        payload['conditions'].update(category='체육',region='강서구',age=70,time_slot='오전',budget_amount=0,mobility='이동 적게')
        payload['update_fields']=['category','region','age','time_slot','budget_amount','mobility']
        client=Mock();client.models.generate_content.return_value=NS(prompt_feedback=None,candidates=[NS(finish_reason='STOP')],text=json.dumps(payload))
        state=handle_turn(new_state(),'70세 강서구 오전 무료 운동 추천해줘. 이동 적게 하고 싶어',self.rows,Settings(gemini_api_key='mock'),client=client,as_of=DAY)
        self.assertEqual(state['mode'],'gemini')
        self.assertEqual(state['code'],'ideas')
        self.assertIsNone(state['diagnostic'])
        self.assertEqual(state['conditions']['age'],70)
        self.assertTrue(all(x['near_home'] for x in state['ideas']))
        self.assertFalse(state['results'])

    def test_broad_activity_request_varies_categories_and_other_activity_rotates(self):
        state=self.turn(new_state(),'할 수 있는 활동 추천해줘')
        self.assertEqual({x['category'] for x in state['ideas']},{'체육','문화·취미','평생학습'})
        before={x['id'] for x in state['ideas']}
        state=self.turn(state,'다른 활동')
        self.assertNotEqual(before,{x['id'] for x in state['ideas']})
        self.assertNotIn('activity_type',state['conditions'])

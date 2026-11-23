"""Nationwide snapshot and genuinely generated conversation: all providers mocked."""
from copy import deepcopy
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch,Mock
import json
from types import SimpleNamespace as NS
from services.regions import data,provinces,districts,neighbourhoods,selection,resolve
from services.conversation_ai import validate_plan,understand
from services.ai import empty_extraction,AIError
from services.dialogue import new_state
from services.discovery import discovery_turn
from services.activities import load_activities
from services.config import Settings
from services.web_search import same_search_area


def plan(route,answer,hobbies=(),**conditions):
 extraction=empty_extraction();extraction['conditions'].update(conditions);extraction['update_fields']=list(conditions)
 return dict(route=route,reply=answer,hobbies=list(hobbies),idea_ids=[],extraction=extraction)

def hobby(name):return dict(name=name,reason='함께 배우며 이야기 나눌 수 있는 취미예요.',start='입문 방법부터 천천히 알아보세요.',materials='준비할 도구를 먼저 확인하세요.',cost_note='추가 구매 전에 확인하세요.')

class NationalRegionsTest(TestCase):
 def test_complete_hierarchy_and_provenance(self):
  self.assertEqual(len(provinces()),17);self.assertEqual(len(data()['regions']),3558)
  self.assertEqual(data()['metadata']['snapshot_at'],'2026-04-01');self.assertIn('sgis',data()['metadata']['official_origin'])
  for province in provinces():
   self.assertTrue(districts(province))
   for district in districts(province):self.assertTrue(neighbourhoods(province,district))
 def test_every_code_is_unique_and_no_orphan(self):
  for row in data()['regions']:
   selected=selection(*row[2:]);self.assertEqual(selected['code'],row[0]);self.assertEqual(selected['kind'],'administrative')
 def test_county_non_autonomous_gu_and_special_city(self):
  self.assertIn('화성시 동탄구',districts('경기도'));self.assertIn('동탄1동',neighbourhoods('경기도','화성시 동탄구'))
  self.assertIn('조치원읍',neighbourhoods('세종특별자치시','세종시'));self.assertTrue(any(n.endswith('면') for r in data()['regions'] for n in [r[4]]))
 def test_legal_dong_never_receives_fake_admin_code(self):
  loc=resolve('부산 해운대구 우동');self.assertEqual(loc['neighbourhood'],'우동');self.assertIsNone(loc['code']);self.assertEqual(loc['kind'],'user_text')
  self.assertEqual(resolve('부산해운대구우동')['neighbourhood'],'우동');self.assertEqual(resolve('서울강서구화곡동')['neighbourhood'],'화곡동')
  self.assertIn('우1동',neighbourhoods('부산광역시','해운대구'));self.assertNotIn('우동',neighbourhoods('부산광역시','해운대구'))
 def test_ambiguous_dong_and_activity_do_not_assign_region(self):
  for text in ('수영 배우고 싶어요','요즘 심심해','몸을 움직이고 싶어요','중동에 살아요','화곡동에 살아요','동탄에서 수영 배우고 싶어'):
   self.assertIsNone(resolve(text))
 def test_ambiguous_city_and_county_are_not_assigned_to_previous_location(self):
  for text in ('광주에서 수영 배우고 싶어요','고성군에서 운동 찾아줘'):
   loc=resolve(text);self.assertTrue(loc['ambiguous']);self.assertIsNone(loc['city'])
  self.assertEqual(resolve('광주광역시에서 수영')['province'],'광주광역시')
  self.assertEqual(resolve('경기도 광주시에서 수영')['province'],'경기도')
 def test_invalid_selection_is_rejected(self):
  self.assertRaises(ValueError,selection,'부산광역시','강서구','우1동')
 def test_region_guard_distinguishes_same_county_in_other_province(self):
  loc=selection('강원특별자치도','고성군','간성읍')
  self.assertTrue(same_search_area({'address':'강원도 고성군 간성읍 1'},loc));self.assertFalse(same_search_area({'address':'경상남도 고성군 고성읍'},loc))
  loc=selection('경기도','화성시 동탄구','동탄1동')
  self.assertFalse(same_search_area({'address':'경기도 광주시 경안동'},dict(province='광주광역시',city='광주',district=None,neighbourhood=None)))
  self.assertTrue(same_search_area({'address':'광주광역시 동구 충장동'},dict(province='광주광역시',city='광주',district='동구',neighbourhood='충장동')))
  self.assertTrue(same_search_area({'address':'경기도 화성시 동탄구 동탄1동'},loc));self.assertFalse(same_search_area({'address':'경기도 화성시 동탄구 반송동'},loc))

class FreeConversationTest(TestCase):
 def setUp(self):self.rows=load_activities();self.settings=Settings(gemini_api_key='mock-only',tavily_api_key='mock-search-only');self.state=dict(new_state(),life_mode=True,web_enabled=True)
 def say(self,text,payload):
  with patch('services.conversation_ai.understand',return_value=validate_plan(payload)):
   self.state,_=discovery_turn(self.state,text,self.rows,self.settings)
  return self.state
 def test_contextual_counselling_then_local_search(self):
  with patch('services.live_discovery.search') as search,patch('services.live_discovery.cache_search') as cache:
   s=self.say('요즘 심심해',plan('explore','어떤 시간을 보내고 싶으세요? 혼자 즐기거나 함께하는 취미를 생각해 볼 수 있어요.',[hobby('그림'),hobby('합창')]))
   self.assertNotIn('region',s['conditions']);self.assertEqual(s['mode'],'gemini')
   s=self.say('사람들 만나고 싶어',plan('explore','함께 배우는 활동이 끌리시는군요. 합창이나 춤을 생각해 볼 수 있어요.',[hobby('댄스'),hobby('합창')],companionship='함께',purpose='교류'))
   s=self.say('춤은 잘 못 춰',plan('howto','실력이 걱정되시는군요. 입문 동작부터 천천히 익히는 방법도 있어요.',[hobby('댄스')],activity_type='댄스'))
   self.assertIn('입문 동작',s['message']);self.assertEqual(s['conditions']['activity_type'],'댄스');search.assert_not_called();cache.assert_not_called()
  s=self.say('좋아. 근처에 있어?',plan('search','배울 곳을 찾는 데 필요한 동네를 확인할게요.'))
  self.assertEqual(s['pending'],'region')
  with patch('services.live_discovery.search') as search:
   search.side_effect=lambda state,*a,**kw:dict(state,web={'status':'empty','rows':[]})
   s=self.say('부산 해운대구 우동',plan('search','원하시는 동네 조건을 반영할게요.',region='부산 해운대구',neighbourhood='우동'))
   search.assert_called_once();self.assertEqual(s['location']['city'],'부산');self.assertEqual(s['location']['district'],'해운대구');self.assertIsNone(s['location']['code'])
 def test_home_advice_and_personalised_model_text_not_template(self):
  self.state['conditions'].update(activity_type='수영',category='체육',purpose='운동',region='인천',budget_amount=0)
  answer='스마트폰으로 일상을 사진에 담고 짧은 글을 붙여보세요. 어떤 장면을 남기고 싶으세요?'
  with patch('services.live_discovery.search') as search:
   s=self.say('혼자 집에서 할 수 있는 취미는?',plan('home',answer,[hobby('스마트폰 사진 일기')],companionship='혼자'))
  self.assertEqual(s['message'],answer);self.assertEqual(s['ideas'][0]['name'],'스마트폰 사진 일기');search.assert_not_called();self.assertNotIn('activity_type',s['conditions']);self.assertNotIn('purpose',s['conditions']);self.assertEqual(s['conditions']['region'],'인천');self.assertEqual(s['conditions']['budget_amount'],0)
 def test_arbitrary_fluent_text_and_one_question_are_supported(self):
  from services.life_assistant import grounded_request
  req=grounded_request('춤이나 합창 중 어떤 게 좋을까?',self.state,empty_extraction())
  self.assertNotIn('activity_type',req['update_fields'])
  validate_plan(plan('explore','함께 시간을 보낼 새로운 취미를 찾아봐요. 노래나 그림 중 무엇이 끌리세요?',[hobby('합창')]))
  for unsafe in ('전화 02-1234-5678로 연락하세요.','행복문화센터에 가세요.','회당 5000원이에요.','신청이 완료됐어요.','모든 어르신에게 안전해요.'):
   with self.subTest(unsafe=unsafe),self.assertRaises(AIError):validate_plan(plan('explore',unsafe))
  with self.assertRaises(AIError):validate_plan(plan('explore','혼자가 좋으세요? 함께가 좋으세요?'))
 def test_failure_is_labelled_as_basic_not_generated_chat(self):
  with patch('services.conversation_ai.understand',side_effect=AIError(code='timeout')):
   s,_=discovery_turn(self.state,'취미가 없는데 뭘 하면 좋을까?',self.rows,self.settings)
  self.assertEqual(s['mode'],'fallback');self.assertTrue(s['ai_unavailable']);self.assertIn('AI와 연결되지 않아',s['message']);self.assertEqual(s['counselling_mode'],'basic');self.assertTrue(s['ideas']);self.assertEqual(s['history'][-1]['content'],s['message'])
 def test_generated_hobby_selection_contains_no_programme_fact_fields(self):
  s=self.say('친구를 사귀고 싶어',plan('explore','함께하는 취미를 생각해 봐요.',[hobby('합창')]))
  self.assertTrue(s['ideas'][0]['general']);self.assertNotIn('official_url',s['ideas'][0]);self.assertFalse(s['results'])
 def test_identical_answered_question_is_not_repeated(self):
  self.say('취미를 모르겠어',plan('explore','함께하는 취미도 생각해 봐요. 혼자가 좋으세요?',[hobby('그림')]))
  s=self.say('혼자 하고 싶어',plan('explore','그리는 취미를 시작해 봐요. 혼자가 좋으세요?',[hobby('그림')],companionship='혼자'))
  self.assertNotIn('혼자가 좋으세요?',s['message']);self.assertEqual(s['conditions']['companionship'],'혼자')
 def test_no_programmes_then_refusal_continues_counselling_without_search(self):
  self.state.update(web={'status':'empty','rows':[]},conversation_route='search')
  with patch('services.live_discovery.search') as search:
   s=self.say('다른 거 없을까?',plan('explore','집에서 시작할 다른 취미도 살펴봐요.',[hobby('종이 접기')]))
  search.assert_not_called();self.assertNotIn('web',s);self.assertTrue(s['ideas']);self.assertIn('다른 취미',s['message'])
 def test_real_sdk_request_has_free_reply_schema_and_context(self):
  client=Mock();payload=plan('explore','어떤 취미가 끌리시는지 함께 살펴봐요.',[hobby('합창')])
  client.models.generate_content.return_value=NS(text=json.dumps(payload),candidates=[NS(finish_reason='STOP')],prompt_feedback=None)
  result=understand('새로운 걸 배우고 싶어요',self.state,self.rows,self.settings,client=client)
  args=client.models.generate_content.call_args.kwargs;self.assertNotIn('enum',args['config'].response_json_schema['properties']['reply']);self.assertIn('previous_hobbies',json.loads(args['contents']));self.assertEqual(result['reply'],payload['reply'])

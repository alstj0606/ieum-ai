"""Natural conversation/search boundary; Gemini and transport are deterministic mocks."""
from copy import deepcopy
from types import SimpleNamespace as NS
import json
from unittest import TestCase
from unittest.mock import patch, Mock
from services.activities import load_activities
from services.ai import AIError, empty_extraction
from services.config import Settings
from services.dialogue import new_state, basic_extract, manual_search
from services.discovery import discovery_turn, visible_activities
from services.life_assistant import public_search
from services.conversation_ai import understand, validate_plan
from services.web_search import SearchError


def initial():return dict(new_state(),life_mode=True,web_enabled=True)

class LifeAssistantTest(TestCase):
 def setUp(self):self.rows=load_activities();self.settings=Settings()
 def say(self,state,text,**kw):return discovery_turn(state,text,self.rows,kw.pop('settings',self.settings),**kw)[0]
 def test_no_default_location_or_manual_search_default(self):
  s=initial();self.assertFalse(s['conditions'])
  s=self.say(s,'수영 배우고 싶어요')
  self.assertEqual(s['pending'],'region');self.assertNotIn('region',s['conditions'])
  self.assertEqual(s['location'],dict(city=None,district=None,neighbourhood=None))
  self.assertNotIn('강서',s['message']);self.assertFalse(manual_search(new_state(),self.rows)['results'])
 def test_explicit_city_and_short_dong_go_directly_to_search(self):
  for text in ('부천 중동에서 수영 배우고 싶어요','부천시 중동에서 수영 배우고 싶어요'):
   with patch('services.live_discovery.search') as search:
    search.side_effect=lambda state,*a,**kw:dict(state,web={'status':'empty','rows':[]})
    s=self.say(initial(),text,settings=Settings(tavily_api_key='mock-only'))
    search.assert_called_once();self.assertEqual(s['location']['city'],'부천');self.assertEqual(s['location']['neighbourhood'],'중동');self.assertNotEqual(s['pending'],'web_location')
 def test_region_answer_keeps_previous_activity_and_short_dong(self):
  s=self.say(initial(),'수영 배우고 싶어요');s=self.say(s,'부천시 중동이에요')
  self.assertEqual(s['location']['neighbourhood'],'중동');self.assertEqual(s['conditions']['activity_type'],'수영');self.assertFalse(visible_activities(s))
 def test_hobby_chat_home_and_howto_do_not_search(self):
  for text,route in [('요즘 심심해요','explore'),('사람들 만나면서 할 만한 거 없을까?','explore'),('그림을 처음 배우려면?','howto'),('그냥 집에서 할 수 있는 취미부터 알려줘','home'),('안녕하세요','chat'),('고마워요','chat')]:
   with self.subTest(text=text),patch('services.live_discovery.search') as search,patch('services.live_discovery.cache_search') as cache:
    s=self.say(initial(),text);self.assertEqual(s['conversation_route'],route);search.assert_not_called();cache.assert_not_called();self.assertNotIn('강서',s['message']);self.assertLessEqual(s['message'].count('?'),1)
    if route in {'explore','home'}:self.assertTrue(1<=len(s['ideas'])<=3)
 def test_howto_then_nearby_asks_region_then_keeps_incheon(self):
  s=self.say(initial(),'그림을 처음 배우려면?');s=self.say(s,'가까운 곳도 찾아줘')
  self.assertEqual(s['pending'],'region');s=self.say(s,'인천에 살아요')
  self.assertEqual(s['conditions']['region'],'인천');self.assertEqual(s['conditions']['activity_type'],'미술');self.assertFalse(visible_activities(s));self.assertNotIn('강서',s['message'])
 def test_model_cannot_fabricate_location_or_age(self):
  extraction=empty_extraction();extraction['conditions'].update(region='서울 강서구',neighbourhood='화곡동',age=70);extraction['update_fields']=['region','neighbourhood','age']
  plan=dict(extraction=extraction,route='search',idea_ids=[],reply='')
  with patch('services.conversation_ai.understand',return_value=plan):
   s=self.say(initial(),'수영 배우고 싶어요',settings=Settings(gemini_api_key='mock-only'))
  self.assertNotIn('region',s['conditions']);self.assertNotIn('age',s['conditions']);self.assertEqual(s['pending'],'region')
 def test_failure_has_no_technical_language_or_wrong_region_cache(self):
  with patch('services.live_discovery.search_programs',side_effect=SearchError('free_plan_required')):
   s=self.say(initial(),'인천 부평구 부평동 수영 찾아줘',settings=Settings(tavily_api_key='mock-only'))
  with patch('services.live_discovery.search_programs',side_effect=SearchError('quota')) as retry:
   again=self.say(s,'인터넷 검색 다시 하기',settings=Settings(tavily_api_key='mock-only'));retry.assert_called_once();self.assertEqual(again['conversation_route'],'search')
  s['declined_web_ids']=['previously-refused']
  with patch('services.live_discovery.search_programs',side_effect=SearchError('timeout')) as retry:
   failed=self.say(s,'인터넷 검색 다시 하기',settings=Settings(tavily_api_key='mock-only'))
   self.assertEqual(retry.call_args.kwargs['excluded'],['previously-refused']);self.assertEqual(failed['declined_web_ids'],['previously-refused'])
  self.assertEqual(s['search_failure']['code'],'free_plan_required');self.assertFalse(visible_activities(s))
  self.assertEqual(s['message'],'지금은 새로운 정보를 찾기 어려워요. 다시 찾아볼까요?')
  self.assertEqual(s['conditions']['region'],'인천 부평구')
 def test_budget_rejection_asks_one_question_then_applies_explicit_free(self):
  s=self.say(initial(),'서울 강서구 수영 찾아줘');s=self.say(s,'너무 비싸요')
  self.assertEqual(s['pending'],'life_budget');self.assertNotIn('budget_amount',s['conditions'])
  s=self.say(s,'무료로 찾아줘');self.assertEqual(s['conditions']['budget_amount'],0);self.assertIn('강서구',s['conditions']['region']);self.assertEqual(s['conditions']['activity_type'],'수영')
 def test_far_rejection_asks_dong_and_preserves_conditions(self):
  s=self.say(initial(),'부천 중동 수영 배우고 싶어요');s=self.say(s,'너무 멀어요')
  self.assertEqual(s['pending'],'web_dong');self.assertEqual(s['conditions']['activity_type'],'수영');self.assertEqual(s['conditions']['region'],'부천')
  s=self.say(s,'상동이에요');self.assertEqual(s['location']['neighbourhood'],'상동');self.assertEqual(s['location']['city'],'부천')
 def test_refusal_excludes_visible_programmes_and_ideas(self):
  s=self.say(initial(),'서울 강서구 걷기 프로그램 찾아줘');ids={r['id'] for r in visible_activities(s)};self.assertTrue(ids)
  s=self.say(s,'다른 거 추천해줘');self.assertTrue(ids<=set(s['declined_ids']));self.assertFalse(ids&{r['id'] for r in visible_activities(s)})
  s=self.say(initial(),'요즘 심심해요');ids={i['id'] for i in s['ideas']};s=self.say(s,'다른 거 추천해줘');self.assertFalse(ids&{i['id'] for i in s['ideas']})
 def test_gemini_error_retains_context_and_diagnostic_without_raw_error(self):
  s=self.say(initial(),'부천 중동 수영 배우고 싶어요')
  with patch('services.conversation_ai.understand',side_effect=AIError(code='timeout')):
   s=self.say(s,'오후가 좋아요',settings=Settings(gemini_api_key='mock-only'))
  self.assertEqual(s['mode'],'fallback');self.assertEqual(s['diagnostic']['code'],'timeout');self.assertEqual(s['conditions']['time_slot'],'오후');self.assertEqual(s['conditions']['region'],'부천');self.assertFalse(visible_activities(s))
 def test_incheon_change_removes_old_dong_and_reset_clears_region(self):
  s=self.say(initial(),'서울 강서구 화곡동 수영');s=self.say(s,'인천에 살아요');self.assertEqual(s['conditions']['region'],'인천');self.assertIsNone(s['location']['neighbourhood']);self.assertFalse(visible_activities(s))
  s=self.say(s,'처음부터');self.assertFalse(s['conditions']);self.assertFalse(s['history'])
 def test_cityless_dong_is_not_resolved_using_gangseo_inventory(self):
  s=self.say(initial(),'화곡동 수영 배우고 싶어요');self.assertEqual(s['pending'],'web_location');self.assertIsNone(s['location']['city']);self.assertNotIn('region',s['conditions'])
 def test_safe_logs_do_not_contain_key_or_utterance(self):
  with self.assertLogs('services.life_assistant',level='INFO') as records:
   self.say(initial(),'인천 부평구 수영 찾아줘')
  logs=' '.join(records.output);self.assertNotIn('인천',logs);self.assertNotIn('수영',logs);self.assertIn('key_missing',logs)
 def test_healthy_context_does_not_infer_age_or_health(self):
  s=self.say(initial(),'몸이 뻐근한데 무리하지 않고 운동하고 싶어')
  self.assertEqual(s['conversation_route'],'explore');self.assertEqual(s['conditions']['effort_preference'],'가볍게');self.assertNotIn('age',s['conditions'])

 def test_expansion_requires_consent_and_never_reuses_local_cache(self):
  s=self.say(initial(),'서울 강서구 걷기 프로그램 찾아줘')
  s=self.say(s,'인접 지역도 찾아줘');self.assertEqual(s['pending'],'expand_region')
  with patch('services.live_discovery.search') as search:
   no=self.say(s,'아니요');search.assert_not_called();self.assertEqual(no['conditions']['region'],s['conditions']['region'])
  yes=self.say(s,'네');self.assertFalse(visible_activities(yes));self.assertIn('인접 지역',yes['message'])
 def test_general_plan_controls_open_wording_without_search(self):
  plan=dict(extraction=empty_extraction(),route='home',idea_ids=['craft','garden'],reply='집에서 시작할 수 있는 취미부터 골라봐요.')
  with patch('services.conversation_ai.understand',return_value=plan),patch('services.live_discovery.search') as search:
   s=self.say(initial(),'시간을 조용히 보내고 싶네요',settings=Settings(gemini_api_key='mock-only'))
  self.assertEqual(s['conversation_route'],'home');self.assertEqual(s['mode'],'gemini');search.assert_not_called();self.assertTrue(s['ideas'])
 def test_region_can_be_cleared_without_restoring_previous_city(self):
  s=self.say(initial(),'부천 중동 수영 찾아줘');e=empty_extraction();e['clear_fields']=['region']
  s=self.say(s,'지역은 상관없어요',extraction=e)
  self.assertNotIn('region',s['conditions']);self.assertIsNone(s['location']['city']);self.assertIsNone(s['location']['neighbourhood'])

 def test_howto_yes_keeps_user_words_and_selected_city_survives_picker(self):
  from services.guided_flow import open_picker,choose_city
  s=self.say(initial(),'그림을 처음 배우려면?')
  s,shown=discovery_turn(s,'네',self.rows,self.settings)
  self.assertEqual(shown,'네');self.assertEqual(s['pending'],'region')
  s=choose_city(open_picker(s,'region_city'),'부천')
  self.assertEqual(s['conditions']['region'],'부천')
  s=self.say(s,'수영 배우고 싶어요');self.assertEqual(s['conditions']['region'],'부천');self.assertNotEqual(s['pending'],'region')

class ConversationAIContractTest(TestCase):
 def plan(self):return dict(extraction=empty_extraction(),route='explore',idea_ids=['craft','garden'],reply='그리거나 가꾸는 취미를 생각해 볼 수 있어요.')
 def test_sdk_model_schema_and_no_search_tool_single_call(self):
  client=Mock();client.models.generate_content.return_value=NS(text=json.dumps(self.plan()),candidates=[NS(finish_reason='STOP')],prompt_feedback=None)
  out=understand('요즘 심심해요',initial(),[],Settings(gemini_api_key='mock-only'),client=client)
  self.assertEqual(out['idea_ids'],['craft','garden']);client.models.generate_content.assert_called_once()
  args=client.models.generate_content.call_args.kwargs;self.assertEqual(args['model'],'gemini-2.5-flash');self.assertEqual(args['config'].response_mime_type,'application/json');self.assertFalse(args['config'].tools)
 def test_reject_actionable_facts_and_unknown_ids(self):
  for text in ('가짜센터에서 배워요.','02-1234-5678로 전화해요.','무료 프로그램 신청이 완료됐어요.','https://example.com','서울에서 매일 운동해요.','행복수영교실에 가보세요.'):
   p=self.plan();p['reply']=text
   with self.subTest(text=text),self.assertRaises(AIError):validate_plan(p)
  p=self.plan();p['idea_ids']=['invented'];self.assertRaises(AIError,validate_plan,p)
 def test_provider_error_redacted(self):
  client=Mock();client.models.generate_content.side_effect=TimeoutError('KEY SECRET RAW USER CONTENT')
  with self.assertRaises(AIError) as error:understand('질문',initial(),[],Settings(gemini_api_key='mock-only'),client=client)
  self.assertEqual(error.exception.code,'timeout');self.assertNotIn('SECRET',str(error.exception))

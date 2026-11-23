"""Reproduce reported use flows, including pending-region and old-session paths."""
from copy import deepcopy
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from services.dialogue import new_state
from services.ai import empty_extraction,AIError
from services.config import Settings
from services.activities import load_activities
from services.discovery import discovery_turn
from services.regions import selection,resolve,matching_localities
from services.location_events import confirm_location
from services.runtime_diagnostics import snapshot
from services.conversation_ai import validate_plan

ROOT=Path(__file__).resolve().parents[1]

def payload(route,text):return dict(extraction=empty_extraction(),route=route,reply=text,idea_ids=[],hobbies=[])

class IphoneRegressionTest(TestCase):
 def setUp(self):self.rows=load_activities();self.settings=Settings(gemini_api_key='mock-only')
 def state(self):return dict(new_state(),life_mode=True,web_enabled=True,search_requested=True,pending='region',conversation_route='search',conditions={'activity_type':'수영','budget_amount':0})
 def test_reported_four_questions_interrupt_region_wait_and_use_model_reply(self):
  s=self.state()
  for text,route,answer in [('요즘 취미가 없어서 심심해','explore','새로운 취미를 함께 생각해 봐요. 어떤 시간을 보내고 싶으세요?'),('사람들이랑 할 수 있는 건 없을까?','explore','함께 즐길 활동으로 합창이나 그림 교실을 생각해 볼 수 있어요.'),('처음 배우면 쉬운 건 뭐야?','howto','종이와 연필로 그리기부터 천천히 시작해 보세요.'),('돈 안 들고 할 수 있는 건?','explore','집에 있는 도구를 활용하는 취미를 생각해 볼 수 있어요.')]:
   s['pending']='region';s['search_requested']=True
   p=validate_plan(payload(route,answer))
   with patch('services.conversation_ai.understand',return_value=p) as model,patch('services.live_discovery.search') as search:
    s,_=discovery_turn(s,text,self.rows,self.settings)
   self.assertEqual(s['message'],answer);self.assertIsNone(s['pending']);self.assertFalse(s['search_requested']);self.assertTrue(s['gemini_reply_used']);self.assertEqual(s['ai_call']['status'],'success');search.assert_not_called()
   self.assertIsNone(model.call_args.args[1]['pending'])
  with patch('services.conversation_ai.understand',return_value=payload('search','배울 곳을 확인할게요.')):
   s,_=discovery_turn(s,'우리 동네에서 찾아줘',self.rows,self.settings)
  self.assertEqual(s['pending'],'region');self.assertFalse(s['gemini_reply_used'])
 def test_ordinary_generic_advice_passes_but_invented_facility_does_not(self):
  for sentence in ('그림 교실과 걷기 모임처럼 함께하는 활동을 생각해 보세요.','수영 강습은 입문 방법부터 알아보세요.'):
   validate_plan(payload('explore',sentence))
  self.assertRaises(AIError,validate_plan,payload('explore','행복문화센터에 가세요.'))
 def test_location_question_from_model_is_rejected_in_counselling(self):
  with patch('services.conversation_ai.understand',return_value=payload('search','어느 동네에서 찾아볼까요?')):
   s,_=discovery_turn(self.state(),'처음 배우면 쉬운 건 뭐야?',self.rows,self.settings)
  self.assertFalse(s['gemini_reply_used']);self.assertTrue(s['ai_unavailable']);self.assertEqual(s['ai_call']['stage'],'policy');self.assertNotEqual(s['pending'],'region')
 def test_confirmed_picker_location_is_event_not_nlp_and_preserves_conditions(self):
  for p,d,n in [('강원특별자치도','강릉시','강남동'),('인천광역시','서구','가정1동'),('서울특별시','강서구','화곡1동')]:
   loc=selection(p,d,n);s=self.state();s['conditions']['time_slot']='오후'
   with patch('services.live_discovery.search_programs') as search,patch('services.conversation_ai.understand') as model:
    result=confirm_location(s,loc,self.rows,Settings())
   model.assert_not_called();search.assert_not_called();self.assertEqual(result['location']['code'],loc['code']);self.assertEqual(result['location']['status'],'confirmed');self.assertNotIn(result['pending'],('region','web_location','web_dong'));self.assertEqual(result['conditions']['budget_amount'],0);self.assertEqual(result['conditions']['time_slot'],'오후')
 def test_location_confirmation_returns_to_counselling_when_search_not_requested(self):
  s=self.state();s.update(search_requested=False,pending=None,conversation_route='explore')
  with patch('services.life_assistant.public_search') as search:
   result=confirm_location(s,selection('강원특별자치도','강릉시','강남동'),self.rows,self.settings)
  search.assert_not_called();self.assertEqual(result['conversation_route'],'explore');self.assertIsNone(result['pending'])
 def test_full_gangneung_input_does_not_require_a_gu(self):
  s=self.state()
  with patch('services.conversation_ai.understand',return_value=payload('search','말씀하신 지역을 살펴볼게요.')):
   result,_=discovery_turn(s,'강원특별자치도 강릉시 강남동',self.rows,self.settings)
  self.assertEqual(result['location']['district'],'강릉시');self.assertEqual(result['location']['status'],'confirmed');self.assertNotIn(result['pending'],('region','web_location','web_dong'))
 def test_yes_does_not_guess_an_ambiguous_location_but_accepts_a_single_proposal(self):
  candidates=matching_localities('중동');self.assertGreater(len(candidates),1)
  s=self.state();s.update(pending='location_confirmation',location_candidates=candidates)
  for word in ('응','네','맞아','그래'):
   result,_=discovery_turn(s,word,self.rows,self.settings);self.assertEqual(result['pending'],'location_confirmation');self.assertFalse(result.get('location',{}).get('code'))
  s['location_candidates']=[selection('강원특별자치도','강릉시','강남동')]
  result,_=discovery_turn(s,'응',self.rows,Settings());self.assertEqual(result['location']['status'],'confirmed');self.assertNotEqual(result['pending'],'location_confirmation')
 def test_admin_diagnostics_are_safe_and_match_loaded_source(self):
  info=snapshot(self.state(),self.settings);self.assertNotIn('mock-only',str(info));self.assertNotIn('수영',str(info));self.assertTrue(all(x is True for x in info['loaded_modules_match_disk'].values()))
 def test_legacy_turn_snapshot_cannot_restore_old_engine_after_rerun(self):
  with patch('services.config.load_settings',return_value=self.settings),patch('services.conversation_ai.understand',return_value=payload('explore','함께 즐길 취미를 생각해 봐요.')) as model:
   app=AppTest.from_file(str(ROOT/'app.py')).run();old=new_state();old.update(pending='region',search_requested=True,conditions={'activity_type':'수영'},code='question')
   app.session_state['dialog']=deepcopy(old);app.session_state['turns']=[{'user':'수영','state':deepcopy(old),'turn_id':1}];app.session_state['turn_seq']=1;app.run()
   self.assertTrue(app.session_state['dialog']['life_mode']);app.chat_input(key='chat').set_value('요즘 취미가 없어서 심심해').run()
   self.assertFalse(app.exception);model.assert_called_once();self.assertTrue(app.session_state['dialog']['gemini_reply_used']);self.assertNotEqual(app.session_state['dialog']['pending'],'region')

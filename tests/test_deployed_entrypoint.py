"""Exercise the deployed entrypoint; fake provider success is explicitly synthetic."""
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from services.ai import empty_extraction
from services.config import Settings
from services.dialogue import new_state
from services.life_assistant import turn

ROOT=Path(__file__).resolve().parents[1]

class DeployedEntrypointTest(TestCase):
 def test_app_uses_conversation_engine_not_legacy_dispatch(self):
  def response(text,*args,**kwargs):
   return dict(route='explore',reply='함께 시간을 보내는 취미를 생각해 봐요. 어떤 경험이 궁금하세요?',extraction=empty_extraction(),idea_ids=[],hobbies=[])
  with patch('services.config.load_settings',return_value=Settings(gemini_api_key='synthetic-only')),patch('services.conversation_ai.understand',side_effect=response) as model,patch('services.discovery.discovery_turn',side_effect=AssertionError('legacy dispatch')):
   app=AppTest.from_file(str(ROOT/'app.py')).run()
   # Recreate an old session without a life_mode marker and pending conditions.
   state=new_state();state.update(pending='region',search_requested=True,conversation_route='search')
   app.session_state['dialog']=state
   for text in ('요즘 집에만 있어서 심심해.','사람들이랑 어울리고 싶어.','어떤 걸 하면 즐거울지 같이 생각해줄래?'):
    app.chat_input(key='chat').set_value(text).run()
    self.assertFalse(app.exception);state=app.session_state['dialog']
    self.assertIsNone(state['pending']);self.assertTrue(state['gemini_reply_used'])
    self.assertEqual(state['last_handler'],'services.life_assistant.turn')
    self.assertIn('함께 시간을 보내는 취미',state['message'])
   self.assertEqual(model.call_count,3)
   self.assertTrue(all(call.args[1]['pending'] is None for call in model.call_args_list))
 def test_missing_api_does_not_turn_unrecognised_counselling_into_region_form(self):
  for pending in ('region','web_location','web_dong','life_budget','time_slot'):
   state=dict(new_state(),pending=pending,search_requested=True,conversation_route='search',life_mode=True)
   state['conditions']={'activity_type':'수영'}
   result,_=turn(state,'어떤 걸 하면 즐거울지 같이 생각해줄래?',[],Settings())
   self.assertNotIn(result['pending'],('region','web_location','web_dong'))
   self.assertFalse(result['gemini_reply_used']);self.assertEqual(result['ai_call']['status'],'not_configured')
   self.assertIn('AI와 연결되지 않아',result['message'])
 def test_diagnostics_measure_actual_main_and_legacy_entrypoints(self):
  with patch('services.config.load_settings',return_value=Settings()):
   for entry,enabled in (('app.py',True),('gangseo_app.py',False)):
    app=AppTest.from_file(str(ROOT/entry)).run();self.assertFalse(app.exception)
    self.assertFalse(app.json)
    app.button(key='run_connection_diagnostics').click().run();self.assertFalse(app.exception)
    records=[json.loads(item.value) for item in app.json]
    evidence=next(item for item in records if 'diagnostics_revision' in item)
    self.assertEqual(evidence['entrypoint'],entry);self.assertEqual(evidence['discovery_enabled'],enabled)
    self.assertEqual(evidence['renderer'],'gangseo_app.py')
    self.assertEqual(evidence['picker_version'],'touch-confirm-v3')
    self.assertTrue(all(evidence['loaded_modules_match_disk'].values()))
    self.assertEqual(evidence['engine'],'not_observed') # No fabricated API/engine success before a turn.

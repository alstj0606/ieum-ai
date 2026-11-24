"""Diagnostics must never be a dependency of startup or normal conversation."""
from copy import deepcopy
from pathlib import Path
import sys
from unittest import TestCase
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from services.config import Settings

APP=str(Path(__file__).resolve().parents[1]/'app.py')
PRIVATE='synthetic-private-value-not-for-logs'

class DiagnosticIsolationTest(TestCase):
 def setUp(self):
  self.settings=patch('services.config.load_settings',return_value=Settings())
  self.settings.start();self.addCleanup(self.settings.stop)
 def app(self):
  app=AppTest.from_file(APP).run()
  self.assertFalse(app.exception)
  self.assertEqual(len([b for b in app.button if b.key and b.key.startswith('start_interest_') and b.key.removeprefix('start_interest_').isdigit()]),4)
  return app
 def failure(self,app):
  before=deepcopy(app.session_state['dialog']);turns=deepcopy(app.session_state['turns'])
  with self.assertLogs('ieum.diagnostics',level='ERROR') as logs:
   app.button(key='run_connection_diagnostics').click().run()
  self.assertFalse(app.exception);self.assertFalse(app.json)
  self.assertEqual(app.session_state['dialog'],before);self.assertEqual(app.session_state['turns'],turns)
  self.assertTrue(any('연결 상태는 확인되지 않았어요' in x.value for x in app.warning))
  self.assertNotIn(PRIVATE,str(logs.output));self.assertNotIn(PRIVATE,str([x.value for x in app.warning]))
  self.assertIn('connection_diagnostics_failed',str(logs.output))
  return str(logs.output)
 def test_stale_signature_is_lazy_and_does_not_break_restored_session(self):
  def old_snapshot(state,settings):return {}
  with patch('services.runtime_diagnostics.snapshot',side_effect=old_snapshot) as diagnostic:
   app=self.app();diagnostic.assert_not_called()
   app.chat_input(key='chat').set_value('서울 강서구에서 수영 배우고 싶어요').run()
   app.run();self.assertFalse(app.exception);diagnostic.assert_not_called()
   logs=self.failure(app);self.assertIn('TypeError',logs);self.assertIn('unexpected_keyword_discovery',logs);self.assertEqual(diagnostic.call_count,1)
   app.chat_input(key='chat').set_value('요즘 심심해요').run()
   self.assertFalse(app.exception);self.assertIsNone(app.session_state['dialog']['pending'])
   app.chat_input(key='chat').set_value('수영 배우고 싶어요').run()
   app.button(key='region_change').click().run()
   self.assertFalse(app.exception);self.assertEqual(len([b for b in app.button if b.key and b.key.startswith('region_option_province_')]),17)
   self.assertEqual(diagnostic.call_count,1)
 def test_internal_typeerror_is_contained_and_safely_logged(self):
  with patch('services.runtime_diagnostics.loaded_modules_match_disk',side_effect=TypeError(PRIVATE)) as check:
   app=self.app();check.assert_not_called()
   logs=self.failure(app);self.assertIn('error_type=TypeError',logs);self.assertIn('stage=snapshot',logs)
 def test_json_render_typeerror_is_contained(self):
  with patch('streamlit.json',side_effect=TypeError(PRIVATE)) as display:
   app=self.app();display.assert_not_called()
   logs=self.failure(app);self.assertIn('stage=display',logs)
 def test_diagnostic_import_failure_does_not_block_startup(self):
  with patch.dict(sys.modules,{'services.runtime_diagnostics':None}):
   app=self.app();logs=self.failure(app);self.assertIn('ModuleNotFoundError',logs)

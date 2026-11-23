from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from services.config import Settings

class SpeakerLabelsTest(TestCase):
 def test_owned_role_names_are_kept_on_rerun_with_cards_in_assistant(self):
  with patch('services.config.load_settings',return_value=Settings()):
   app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=15).run()
   self.assertTrue(any('data-ieum-role="assistant"' in x.value and '이음 AI' in x.value for x in app.markdown))
   for text in ('수영을 배우고 싶어요','서울 강서구요'):
    app.chat_input(key='chat').set_value(text).run()
   app.run()
   self.assertFalse(app.exception)
   self.assertTrue(any('data-ieum-role="user">사용자 메시지' in x.value for x in app.chat_message[-2].markdown))
   self.assertTrue(any('data-ieum-role="assistant"' in x.value and '이음 AI' in x.value for x in app.chat_message[-1].markdown))
   self.assertTrue(app.chat_message[-1].subheader)

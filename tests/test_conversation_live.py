"""Explicit opt-in integration; no keys, utterances or raw responses in output."""
import os
from unittest import TestCase,skipUnless
from services.conversation_ai import understand
from services.config import load_settings
from services.dialogue import new_state

@skipUnless(os.getenv('IEUM_RUN_LIVE_GEMINI')=='1' and bool(os.getenv('GEMINI_API_KEY')),'실제 Gemini 키와 IEUM_RUN_LIVE_GEMINI=1 필요')
class LiveConversationTest(TestCase):
 def test_general_counselling_contract(self):
  payload=understand('집에서 시작할 취미를 추천해 주세요.',new_state(),[],load_settings())
  self.assertTrue(payload['route'] in {'home','explore','howto'})
  self.assertTrue(0<len(payload['reply'])<=260)
  self.assertTrue(len(payload.get('hobbies',[]))<=3)

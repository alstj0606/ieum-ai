"""Opt-in real API probe: disabled unless BOTH flag and server key are supplied.

A live zero-result response is valid; this does not assert enrollment or availability.
Never prints credentials, provider responses, or user's conversation.
"""
import os
from unittest import TestCase,skipUnless
from services.config import load_settings
from dataclasses import replace
from services.web_search import search_programs
from services.activities import load_activities
from services.web_search import official_hosts

@skipUnless(os.environ.get('IEUM_RUN_LIVE_SEARCH')=='1' and os.environ.get('BRAVE_SEARCH_API_KEY') and os.environ.get('ALLOW_PAID_SEARCH','').lower()=='true' and os.environ.get('SEARCH_PROVIDER','tavily')=='brave', '실제 검색 키와 명시적 실행 플래그 없음')
class BraveLiveWebSearchTest(TestCase):
 def test_live_api_and_verified_page_contract(self):
  outcome=search_programs(replace(load_settings(),search_provider='brave',allow_paid_search=True),{'city':'서울','district':'강서구','neighbourhood':'화곡동'}, {'activity_type':'수영'},hosts=official_hosts(load_activities()))
  self.assertIn(outcome['status'],{'ok','empty','unverified','page_error'})
  for row in outcome['rows']:
   self.assertEqual(row['source_kind'],'official_web');self.assertTrue(row['verified_at']);self.assertTrue(row['official_url'].startswith('https://'))


@skipUnless(os.environ.get('IEUM_RUN_LIVE_SEARCH')=='1' and os.environ.get('TAVILY_API_KEY') and os.environ.get('SEARCH_PROVIDER','tavily')=='tavily', '실제 Tavily 키와 명시적 실행 플래그 없음')
class TavilyLiveWebSearchTest(TestCase):
 def test_free_account_api_and_page_contract(self):
  outcome=search_programs(replace(load_settings(),search_provider='tavily',allow_paid_search=False),{'city':'서울','district':'강서구','neighbourhood':'화곡동'}, {'activity_type':'수영'},hosts=official_hosts(load_activities()))
  self.assertEqual(outcome['provider'],'tavily')
  self.assertIn(outcome['status'],{'ok','empty','unverified','page_error'})
  for row in outcome['rows']:self.assertEqual(row['source_kind'],'official_web')

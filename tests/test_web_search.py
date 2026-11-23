from copy import deepcopy
from datetime import date
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import json
from streamlit.testing.v1 import AppTest
from services.config import Settings,load_settings
from services.web_search import (search_programs,SearchError,ERRORS,is_official,safe_url,extract_program,validate_program,recruitment_status,Transport)
from services.neighbourhood import location_from,question
from services.live_discovery import before_turn,after_turn,select_web
from services.dialogue import new_state
from services.discovery import discovery_turn
from services.activities import load_activities
from web_fixture import FakeTransport,HTML,URL
from services.search_providers import SearchControl

LOC={'city':'서울','district':'강서구','neighbourhood':'화곡동'}
class WebSearchTest(TestCase):
 def setUp(self):
  self.settings=Settings(search_api_key='test-only-not-a-real-key',search_provider='brave',allow_paid_search=True);self.rows=load_activities()
  patcher=patch('services.search_providers.CONTROL',SearchControl(minute_limit=1000,day_limit=1000,month_limit=1000));patcher.start();self.addCleanup(patcher.stop)
 def search(self,mode='ok',conditions=None):return search_programs(self.settings,LOC,conditions or {'activity_type':'수영'},transport=FakeTransport(mode),control=SearchControl())
 def test_request_and_parsing_do_not_use_snippet_facts(self):
  http=FakeTransport();out=search_programs(self.settings,LOC,{'activity_type':'수영'},transport=http);r=out['rows'][0]
  self.assertEqual(r['fee_amount'],0);self.assertNotIn('999',str(r));self.assertEqual(r['phone'],'02-0000-0000');self.assertTrue(r['application_url']);self.assertEqual(r['source_kind'],'official_web');self.assertIn('verified_at',r)
  self.assertIn('q=',http.requests[0][0]);self.assertEqual(http.requests[0][1]['headers']['X-Subscription-Token'],'test-only-not-a-real-key')
 def test_dynamic_region_changes_query_without_other_city_results(self):
  http=FakeTransport();out=search_programs(self.settings,{'city':'부천'}, {'activity_type':'수영'},transport=http)
  self.assertFalse(out['rows']);self.assertIn('%EB%B6%80%EC%B2%9C',http.requests[0][0])
 def test_http_errors_are_safe_and_distinct(self):
  for mode in ('quota','authentication','timeout'):
   with self.assertRaises(SearchError) as c:self.search(mode)
   self.assertEqual(c.exception.code,mode);self.assertNotIn('private',str(c.exception))
  with self.assertRaises(SearchError):self.search('bad_json')
 def test_no_key_is_not_success_or_no_results(self):
  with self.assertRaises(SearchError) as c:search_programs(Settings(),LOC,{},transport=FakeTransport())
  self.assertEqual(c.exception.code,'not_configured')
 def test_empty_unverified_and_page_error_differ(self):
  self.assertEqual(self.search('empty')['status'],'empty');self.assertEqual(self.search('page_error')['status'],'page_error')
  self.assertEqual(self.search()['references'][0]['official'],False)
 def test_official_host_boundary_and_bad_links(self):
  for url in ('http://city.go.kr/x','https://city.go.kr.evil.org/x','https://user:pw@city.go.kr/x','https://city.go.kr:8080/x','javascript:alert(1)'):
   self.assertFalse(is_official(url))
  self.assertFalse(safe_url('https://127.0.0.1/x'));self.assertFalse(safe_url('https://localhost/x'));self.assertTrue(is_official(URL));self.assertTrue(is_official('https://trusted.or.kr/x',{'trusted.or.kr'}));self.assertFalse(is_official('https://unverified.or.kr/x'))
 def test_private_dns_is_never_requested(self):
  with patch('socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]):
   with self.assertRaises(SearchError):Transport().get(URL)
 def test_redirect_outside_trust_is_not_followed(self):
  from services.web_search import fetch_page
  http=FakeTransport()
  with patch.object(http,'get',return_value=(302,{'location':'https://127.0.0.1/private'},b'')):
   with self.assertRaises(SearchError):fetch_page(URL,set(),http)
 def test_unknown_fee_is_not_free_and_invalid_phone_is_not_linked(self):
  html=HTML.replace('비용: 무료','비용: 확인 필요').replace('02-0000-0000','010-123-INVALID')
  r=extract_program(URL,html,LOC,'수영','2026-11-23T00:00:00+00:00',set(),FakeTransport())
  self.assertIsNone(r['fee_amount']);self.assertIsNone(r['phone'])
 def test_programme_list_and_nonprogramme_page_are_not_cards(self):
  self.assertIsNone(extract_program(URL,'<h1>프로그램 전체 목록</h1>',LOC,None,'now',set(),FakeTransport()))
  html='<script type="application/ld+json">'+json.dumps([{'@type':'Event','name':'A'},{'@type':'Event','name':'B'}])+'</script>'
  self.assertIsNone(extract_program(URL,html,LOC,None,'now',set(),FakeTransport()))
 def test_registration_and_event_dates_not_publication_date(self):
  r=self.search()['rows'][0];r.update(registration_start='2026-01-01',registration_end='2026-01-31',ends_at='2026-12-01',published_at='2026-11-23')
  self.assertEqual(recruitment_status(r,date(2026,11,23)),'접수 마감');r['ends_at']='2026-02-01';self.assertEqual(recruitment_status(r,date(2026,11,23)),'운영 종료')
  r.update(registration_start=None,registration_end=None,ends_at=None);self.assertEqual(recruitment_status(r,date(2026,11,23)),'모집 상태 확인 필요')
 def test_explicit_open_status_requires_consistent_dates(self):
  r=dict(registration_start='2026-11-01',registration_end='2026-11-30',registration_status_text='접수 중')
  self.assertIn('접수 중',recruitment_status(r,date(2026,11,23)));self.assertEqual(recruitment_status(r,date(2026,11,30)),'접수 시각 확인 필요');self.assertEqual(recruitment_status(r,date(2026,12,1)),'접수 마감');r.update(registration_start='2099-01-01',registration_status_text='접수 마감');self.assertEqual(recruitment_status(r,date(2026,11,23)),'접수 마감')
 def test_required_budget_time_and_age_are_not_assumed(self):
  self.assertTrue(self.search(conditions={'activity_type':'수영','budget_amount':0})['rows'])
  self.assertFalse(self.search(conditions={'activity_type':'수영','age':25})['rows'])
  self.assertFalse(self.search(conditions={'activity_type':'수영','time_slot':'오전'})['rows'])
 def test_validate_rejects_bad_money_and_phone(self):
  r=self.search()['rows'][0]
  for key,value in [('fee_amount',True),('phone','bad'),('application_url','http://unsafe.test')]:
   altered=dict(r);altered[key]=value
   with self.assertRaises(SearchError):validate_program(altered)
 def test_location_ambiguity_and_administrative_dong_are_not_resolved_by_guess(self):
  loc=location_from({'neighbourhood':'등촌1동'},'등촌1동에서 수영');self.assertIsNotNone(question(loc));self.assertIsNone(loc['city'])
  loc=location_from({'region':'부천'},'부천에 살아요');self.assertEqual(loc['city'],'부천')
 def test_location_question_then_answer_keeps_activity_and_dong(self):
  s=dict(new_state(),web_enabled=True)
  with patch('services.web_search.Transport',return_value=FakeTransport()):
   s=discovery_turn(s,'화곡동에 살아요. 수영 배우고 싶어요',self.rows,self.settings)[0]
   self.assertEqual(s['pending'],'web_location');self.assertFalse(s['web'].get('rows',[]) if s.get('web') else [])
   s=discovery_turn(s,'서울 강서구요',self.rows,self.settings)[0]
  self.assertEqual(s['conditions']['neighbourhood'],'화곡동');self.assertEqual(s['conditions']['activity_type'],'수영');self.assertTrue(s['web']['rows'])
 def test_selection_refusal_expansion_consent_and_repeat_search(self):
  s=dict(new_state(),code='found',web_enabled=True,conditions={'region':'서울 강서구','neighbourhood':'화곡동','activity_type':'수영'})
  with patch('services.web_search.Transport',return_value=FakeTransport()):
   s=after_turn(s,s,'서울 강서구 화곡동',self.settings,self.rows)
   invalid=before_turn(s,'3번',self.settings,self.rows);self.assertIsNone(invalid['web']['selected_id'])
   s=select_web(s,s['web']['rows'][0]['id']);self.assertEqual(s['code'],'web_detail')
   application=before_turn(s,'이거 어떻게 신청해?',self.settings,self.rows);self.assertEqual(application['web']['selected_id'],s['web']['selected_id'])
   ask=before_turn(s,'다른 동네도 괜찮아요',self.settings,self.rows);self.assertEqual(ask['pending'],'web_expand');self.assertFalse(ask['web']['expanded'])
   no=before_turn(ask,'아니요, 이 동네만 볼게요',self.settings,self.rows);self.assertFalse(no['web']['expanded'])
   yes=before_turn(ask,'네, 다른 동네도 찾아주세요',self.settings,self.rows);self.assertTrue(yes['web']['expanded'])
   rejected=before_turn(s,'이건 별로예요',self.settings,self.rows);self.assertFalse(rejected['web']['rows']);self.assertTrue(rejected['web']['excluded'])
 def test_settings_do_not_print_keys_and_env_wins(self):
  with patch.dict('os.environ',{'BRAVE_SEARCH_API_KEY':'env-only'}):
   cfg=load_settings({'BRAVE_SEARCH_API_KEY':'secret-only'});self.assertEqual(cfg.search_api_key,'env-only');self.assertNotIn('env-only',repr(cfg))
 def test_gemini_failure_keeps_real_search_facts_and_notice(self):
  from services.ai import AIError
  s=dict(new_state(),web_enabled=True)
  with patch('services.dialogue.extract_conditions',side_effect=AIError(code='timeout')),patch('services.web_search.Transport',return_value=FakeTransport()):
   s=discovery_turn(s,'서울 강서구 화곡동 수영',self.rows,Settings(gemini_api_key='fake',search_api_key='fake',search_provider='brave',allow_paid_search=True))[0]
  self.assertEqual(s['mode'],'fallback');self.assertTrue(s['web']['rows'])
 def test_font_menu_native_callback_preserves_dialogue(self):
  with patch('services.config.load_settings',return_value=Settings()):
   app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=15).run();before=deepcopy(app.session_state['dialog'])
   app.button(key='font_settings').click().run();app.button(key='font_choice_2').click().run();self.assertEqual(app.session_state['font_level'],2);self.assertFalse(app.session_state['font_menu']);self.assertEqual(app.session_state['dialog'],before);self.assertFalse(app.exception)

 def test_conflicting_prices_remain_unknown_not_free(self):
  html=HTML.replace('"organizer"','"offers":{"price":1000,"priceCurrency":"KRW"},"organizer"')
  r=extract_program(URL,html,LOC,'수영','2026-11-23T00:00:00+00:00',set(),FakeTransport())
  self.assertIsNone(r['fee_amount']);self.assertIn('확인 필요',r['fee_text'])
 def test_malformed_structured_type_is_not_a_programme(self):
  html='<script type="application/ld+json">{"@type":null,"name":"anything"}</script>'
  self.assertIsNone(extract_program(URL,html,LOC,None,'now',set(),FakeTransport()))
 def test_labelled_public_page_without_jsonld(self):
  html='<main><dl><dt>프로그램명</dt><dd>화곡 수영</dd><dt>주소</dt><dd>서울 강서구 화곡동</dd><dt>비용</dt><dd>무료</dd></dl></main>'
  r=extract_program(URL,html,LOC,'수영','2026-11-23T00:00:00+00:00',set(),FakeTransport())
  self.assertEqual(r['name'],'화곡 수영');self.assertEqual(r['fee_amount'],0)
 def test_dead_application_link_has_no_action_button_data(self):
  http=FakeTransport();original=http.get
  def get(url,**kw):return (404,{},b'') if url.endswith('/program/apply') else original(url,**kw)
  with patch.object(http,'get',side_effect=get):out=search_programs(self.settings,LOC,{'activity_type':'수영'},transport=http)
  self.assertIsNone(out['rows'][0]['application_url'])
 def test_different_neighbourhood_needs_expansion_consent(self):
  http=FakeTransport(html=HTML.replace('화곡동','등촌동'))
  out=search_programs(self.settings,LOC,{'activity_type':'수영'},transport=http);self.assertFalse(out['rows'])
  out=search_programs(self.settings,LOC,{'activity_type':'수영'},transport=http,expanded=True);self.assertTrue(out['rows']);self.assertIn('확인 필요',out['rows'][0]['relation'])
 def test_same_city_but_different_district_is_not_local(self):
  http=FakeTransport(html=HTML.replace('강서구','마포구'))
  self.assertFalse(search_programs(self.settings,LOC,{'activity_type':'수영'},transport=http)['rows'])
 def test_confirming_city_only_still_asks_district_when_dong_ambiguous(self):
  self.assertIsNotNone(question({'city':'서울','district':None,'neighbourhood':'신정동'}))
 def test_keyless_cache_refusal_never_calls_live_transport(self):
  s=dict(new_state(),web={'status':'not_configured','rows':[]})
  with patch('services.web_search.Transport') as transport:self.assertIsNone(before_turn(s,'이건 별로예요',Settings(),self.rows));transport.assert_not_called()

 def test_explicit_cache_fallback_preserves_conditions_and_never_calls_search(self):
  from services.live_discovery import cache_search
  s=dict(new_state(),conditions={'region':'강서구','neighbourhood':'화곡동','category':'문화·취미','time_slot':'오후'},web={'status':'timeout','rows':[]})
  with patch('services.web_search.Transport') as transport:r=cache_search(s,self.rows);transport.assert_not_called()
  self.assertEqual(r['conditions'],s['conditions']);self.assertNotIn('web',r);self.assertIn('인터넷 검색 결과가 아니에요',r['message'])
 def test_cache_does_not_replace_other_city_with_gangseo(self):
  from services.live_discovery import cache_search
  r=cache_search(dict(new_state(),conditions={'region':'부천','activity_type':'수영'}),self.rows)
  self.assertEqual(r['conditions']['region'],'부천');self.assertFalse(r['results']);self.assertFalse(r['references'])

 def test_condition_question_hides_previous_live_cards_without_losing_region(self):
  s=dict(new_state(),code='found',web_enabled=True,conditions={'region':'서울 강서구','neighbourhood':'화곡동','activity_type':'수영'})
  with patch('services.web_search.Transport',return_value=FakeTransport()):
   s=after_turn(s,s,'서울 강서구 화곡동',self.settings,self.rows)
   for command in ('다른 시간','다른 활동'):
    changed=discovery_turn(deepcopy(s),command,self.rows,self.settings)[0]
    self.assertNotIn('web',changed);self.assertEqual(changed['conditions']['region'],s['conditions']['region']);self.assertFalse(changed['results'])
 def test_unknown_fee_unit_is_not_compared_to_monthly_budget(self):
  http=FakeTransport(html=HTML.replace('비용: 무료','비용: 1000원'))
  outcome=search_programs(self.settings,LOC,{'activity_type':'수영','budget_amount':10000,'budget_unit':'월'},transport=http)
  self.assertFalse(outcome['rows']);self.assertTrue(outcome['references'])

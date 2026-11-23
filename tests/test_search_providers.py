from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch
import json
from services.config import Settings,load_settings
from services.search_providers import SearchControl,search_hits,verify_free_plan,TAVILY_SEARCH,TAVILY_USAGE
from services.web_search import SearchError,search_programs,Transport
from services.activities import load_activities
from services.live_discovery import after_turn
from services.dialogue import new_state
from web_fixture import TavilyTransport,HTML

LOC={'city':'서울','district':'강서구','neighbourhood':'화곡동'}
FREE={'key':{'usage':0,'limit':1000},'account':{'current_plan':'Researcher','plan_usage':0,'plan_limit':1000,'paygo_usage':0,'paygo_limit':0}}
class ProvidersTest(TestCase):
 def setUp(self):self.settings=Settings(tavily_api_key='fake-key-not-real');self.http=TavilyTransport();self.control=SearchControl()
 def search(self,query='서울 화곡동 수영'):
  return search_hits(self.settings,query,self.http,control=self.control)
 def test_tavily_basic_only_no_generated_facts_or_paid_tools(self):
  hits,cached,provider=self.search();self.assertEqual(provider,'tavily');self.assertFalse(cached)
  request=next(kw for url,kw in self.http.requests if url==TAVILY_SEARCH);data=json.loads(request['body'])
  self.assertEqual(data['search_depth'],'basic');self.assertFalse(data['auto_parameters']);self.assertFalse(data['include_answer']);self.assertFalse(data['include_raw_content'])
  self.assertNotIn('fake-key-not-real',request['body'].decode());self.assertNotIn('answer',str(hits))
  with self.assertRaises(SearchError):Transport().post('https://fixture.go.kr/apply',body=b'not a form submit')
 def test_secrets_environment_and_key_repr(self):
  with patch.dict('os.environ',{'TAVILY_API_KEY':'from-env'},clear=True):
   settings=load_settings({'TAVILY_API_KEY':'from-secrets'});self.assertEqual(settings.tavily_api_key,'from-env');self.assertNotIn('from-env',repr(settings))
  with patch.dict('os.environ',{},clear=True):
   settings=load_settings({'TAVILY_API_KEY':'from-secrets'});self.assertEqual(settings.tavily_api_key,'from-secrets');self.assertFalse(settings.allow_paid_search)
   self.assertFalse(load_settings({'ALLOW_PAID_SEARCH':1}).allow_paid_search)
 def test_brave_requires_both_selection_and_explicit_paid_permission(self):
  for settings,code in [(Settings(search_api_key='fake'),'not_configured'),(Settings(search_api_key='fake',search_provider='brave'),'paid_disabled')]:
   with self.assertRaises(SearchError) as c:search_hits(settings,'q',self.http,control=self.control)
   self.assertEqual(c.exception.code,code)
  self.assertFalse(self.http.requests)
 def test_no_automatic_brave_fallback_when_tavily_quota_exhausted(self):
  settings=replace(self.settings,search_api_key='brave-fake',allow_paid_search=True)
  http=TavilyTransport(mode='quota')
  with self.assertRaises(SearchError) as c:search_hits(settings,'q',http,control=self.control)
  self.assertEqual(c.exception.code,'quota');self.assertTrue(all(not url.startswith('https://api.search.brave.com') for url,_ in http.requests))
 def test_ttl_cache_reuses_hits_and_returns_independent_copies(self):
  now=[0];self.control=SearchControl(clock=lambda:now[0]);a,_,_=self.search();a[0]['title']='mutated'
  b,cached,_=self.search();self.assertTrue(cached);self.assertNotEqual(b[0]['title'],'mutated')
  self.assertEqual(sum(url==TAVILY_SEARCH for url,_ in self.http.requests),1)
  now[0]=601;self.search();self.assertEqual(sum(url==TAVILY_SEARCH for url,_ in self.http.requests),2)
 def test_concurrent_duplicate_queries_spend_one_search(self):
  with ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(lambda _:self.search(),range(6)))
  self.assertEqual(sum(url==TAVILY_SEARCH for url,_ in self.http.requests),1);self.assertEqual(sum(not r[1] for r in results),1)
 def test_three_per_minute_hits_are_not_charged_again(self):
  for i in range(3):self.search('q'+str(i))
  self.search('q0')
  with self.assertRaises(SearchError) as c:self.search('q4')
  self.assertEqual(c.exception.code,'request_limit');self.assertEqual(sum(url==TAVILY_SEARCH for url,_ in self.http.requests),3)
 def test_daily_and_monthly_caps_and_rollover(self):
  day=['2026-11-23'];now=[0];control=SearchControl(day=lambda:day[0],clock=lambda:now[0],minute_limit=100,day_limit=2,month_limit=3)
  get=lambda q:search_hits(self.settings,q,self.http,control=control)
  get('a');get('b')
  with self.assertRaises(SearchError):get('c')
  day[0]='2026-11-24';now[0]=100;get('c')
  with self.assertRaises(SearchError):get('d')
  day[0]='2026-12-01';now[0]=200;get('d')
 def test_quota_negative_cache_does_not_hammer_provider(self):
  self.http=TavilyTransport(mode='quota')
  for _ in range(3):
   with self.assertRaises(SearchError):self.search()
  self.assertEqual(sum(url==TAVILY_SEARCH for url,_ in self.http.requests),1)
 def test_usage_guard_rejects_paid_plan_or_paygo(self):
  for changes in ({'current_plan':'Bootstrap'},{'paygo_limit':1},{'paygo_usage':1}):
   data=deepcopy(FREE);data['account'].update(changes)
   with self.assertRaises(SearchError) as c:verify_free_plan(data)
   self.assertEqual(c.exception.code,'free_plan_required')
 def test_exhausted_free_or_per_key_limit(self):
  for changes in ({'account':{'plan_usage':1000}},{'key':{'usage':1000}}):
   data=deepcopy(FREE)
   for k,v in changes.items():data[k].update(v)
   with self.assertRaises(SearchError) as c:verify_free_plan(data)
   self.assertEqual(c.exception.code,'quota')
 def test_unknown_usage_fails_closed_before_post(self):
  original=self.http.get
  def get(url,**kw):return (200,{},b'{"account":{}}') if url==TAVILY_USAGE else original(url,**kw)
  with patch.object(self.http,'get',side_effect=get):
   with self.assertRaises(SearchError) as c:self.search()
  self.assertEqual(c.exception.code,'usage_unavailable');self.assertFalse(any(url==TAVILY_SEARCH for url,_ in self.http.requests))
 def test_cache_never_stores_raw_credentials(self):
  self.search();self.assertNotIn(self.settings.tavily_api_key,str(self.control.cache));self.assertNotIn(self.settings.tavily_api_key,str(self.control.budgets))
 def test_account_cache_isolation(self):
  self.search();search_hits(replace(self.settings,tavily_api_key='different-key'),'서울 화곡동 수영',self.http,control=self.control)
  self.assertEqual(sum(url==TAVILY_SEARCH for url,_ in self.http.requests),2)
 def test_official_page_is_refetched_after_cached_search(self):
  a=search_programs(self.settings,LOC,{'activity_type':'수영'},transport=self.http,control=self.control)
  self.http.html=HTML.replace('비용: 무료','비용: 2000원')
  b=search_programs(self.settings,LOC,{'activity_type':'수영'},transport=self.http,control=self.control)
  self.assertTrue(b['cache_hit']);self.assertEqual(a['rows'][0]['fee_amount'],0);self.assertEqual(b['rows'][0]['fee_amount'],2000)
 def test_missing_key_and_limits_keep_region_and_fall_back_to_stored_data(self):
  state=dict(new_state(),code='found',web_enabled=True,conditions={'region':'부천','activity_type':'수영'})
  for settings in (Settings(),self.settings):
   with patch('services.web_search.Transport',return_value=TavilyTransport(mode='quota')),patch('services.search_providers.CONTROL',SearchControl()):result=after_turn(state,state,'부천에서 수영',settings,load_activities())
   self.assertEqual(result['conditions']['region'],'부천');self.assertFalse(result['results']);self.assertIn('저장 자료',result['message']);self.assertIn('search_failure',result)
 def test_legacy_official_data_not_modified(self):
  self.assertEqual(len(load_activities()),10)

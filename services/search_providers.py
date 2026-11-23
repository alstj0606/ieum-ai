"""Search adapters and process-local cost controls, independent of fact extraction.

No paid fallback is automatic. Raw search hits alone are cached, not user state,
program facts, or API credentials. Official pages are verified again downstream.
"""
from collections import OrderedDict,deque
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,hmac,json,os,threading,time
from urllib.parse import urlencode
from services.web_search import SearchError,ENDPOINT

TAVILY_SEARCH='https://api.tavily.com/search'
TAVILY_USAGE='https://api.tavily.com/usage'
_SALT=os.urandom(32)

def credentials(settings):
 provider=settings.search_provider
 if provider not in ('tavily','brave'):raise SearchError('configuration')
 key=settings.tavily_api_key if provider=='tavily' else settings.search_api_key
 if not key:raise SearchError('not_configured')
 if provider=='brave' and not settings.allow_paid_search:raise SearchError('paid_disabled')
 return provider,key

class SearchControl:
 """Atomic single-flight + LRU TTL cache + conservative per-key attempt caps.

Counters are memory-only, per process. Tavily's account preflight and disabled
Pay-as-you-go are the billing boundary across restarts/other apps/workers.
"""
 def __init__(self,*,clock=time.monotonic,day=None,minute_limit=3,day_limit=30,month_limit=900,ttl=600,max_entries=256):
  self.clock=clock;self.day=day or (lambda:datetime.now(timezone.utc).strftime('%Y-%m-%d'))
  self.limits=(minute_limit,day_limit,month_limit);self.ttl=ttl;self.max_entries=max_entries
  self.lock=threading.RLock();self.cache=OrderedDict();self.budgets=OrderedDict()
 def run(self,provider,key,query,compute):
  account=hmac.new(_SALT,(provider+'\0'+key).encode(),hashlib.sha256).hexdigest()
  fingerprint=hmac.new(_SALT,(account+'\0'+query+'\0basic-v1').encode(),hashlib.sha256).hexdigest()
  # One bounded lock also coalesces simultaneous identical queries: no duplicate credit.
  with self.lock:
   now=self.clock();entry=self.cache.get(fingerprint)
   if entry and now<entry['expires']:
    self.cache.move_to_end(fingerprint)
    if entry.get('error'):raise SearchError(entry['error'])
    return deepcopy(entry['hits']),True
   self.cache.pop(fingerprint,None)
   date=self.day();month=date[:7]
   if account not in self.budgets and len(self.budgets)>=256:raise SearchError('request_limit')
   budget=self.budgets.setdefault(account,dict(recent=deque(),day=date,daily=0,month=month,monthly=0))
   self.budgets.move_to_end(account)
   if budget['day']!=date:budget.update(day=date,daily=0)
   if budget['month']!=month:budget.update(month=month,monthly=0)
   while budget['recent'] and now-budget['recent'][0]>=60:budget['recent'].popleft()
   if len(budget['recent'])>=self.limits[0] or budget['daily']>=self.limits[1] or budget['monthly']>=self.limits[2]:raise SearchError('request_limit')
   budget['recent'].append(now);budget['daily']+=1;budget['monthly']+=1
   try:hits=compute()
   except SearchError as error:
    self.cache[fingerprint]={'expires':now+60,'error':error.code}
    self._trim();raise
   self.cache[fingerprint]={'expires':self.clock()+self.ttl,'hits':deepcopy(hits)}
   self._trim();return deepcopy(hits),False
 def _trim(self):
  while len(self.cache)>self.max_entries:self.cache.popitem(last=False)

CONTROL=SearchControl()

def response(status,body):
 if status in (401,403):raise SearchError('authentication')
 if status in (429,432,433):raise SearchError('quota')
 if status!=200:raise SearchError('api_error')
 try:
  value=json.loads(body)
  if not isinstance(value,dict):raise ValueError()
  return value
 except (ValueError,TypeError):raise SearchError('api_error') from None

def verify_free_plan(data):
 account=data.get('account');key=data.get('key')
 if not isinstance(account,dict) or not isinstance(key,dict):raise SearchError('usage_unavailable')
 plan=account.get('current_plan');used=account.get('plan_usage');limit=account.get('plan_limit')
 paygo=account.get('paygo_limit');paygo_used=account.get('paygo_usage')
 if not isinstance(plan,str) or plan.lower() not in ('researcher','free','free tier') or type(paygo) is not int or type(paygo_used) is not int or paygo!=0 or paygo_used!=0:raise SearchError('free_plan_required')
 if type(used) is not int or type(limit) is not int or not 0<limit<=1000 or used<0:raise SearchError('usage_unavailable')
 if used>=limit:raise SearchError('quota')
 key_used=key.get('usage');key_limit=key.get('limit')
 if type(key_used) is not int or key_used<0:raise SearchError('usage_unavailable')
 if key_limit is not None:
  if type(key_limit) is not int or key_limit<0:raise SearchError('usage_unavailable')
  if key_used>=key_limit:raise SearchError('quota')

def search_hits(settings,query,transport,*,control=None):
 provider,key=credentials(settings)
 def request():
  try:
   if provider=='tavily':
    headers={'Authorization':'Bearer '+key}
    if not settings.allow_paid_search:
     status,_,body=transport.get(TAVILY_USAGE,headers=headers,timeout=6,max_bytes=64000)
     verify_free_plan(response(status,body))
    payload=dict(query=query,search_depth='basic',auto_parameters=False,max_results=8,
                 topic='general',include_answer=False,include_raw_content=False,include_images=False)
    status,_,body=transport.post(TAVILY_SEARCH,body=json.dumps(payload).encode(),headers={**headers,'Content-Type':'application/json'},timeout=8,max_bytes=1000000)
    hits=response(status,body).get('results')
   else:
    status,_,body=transport.get(ENDPOINT+'?'+urlencode({'q':query,'country':'KR','search_lang':'ko','count':8}),headers={'X-Subscription-Token':key},timeout=8,max_bytes=1000000)
    hits=response(status,body).get('web',{}).get('results')
   if not isinstance(hits,list):raise SearchError('api_error')
   # Never retain generated answer/raw_content: only the existing search-hit contract.
   return [dict(url=h.get('url'),title=h.get('title'),age=h.get('published_date') or h.get('age')) for h in hits[:8] if isinstance(h,dict)]
  except SearchError as e:
   if e.code=='page_error':raise SearchError('api_error') from None
   raise
  except (TypeError,ValueError,AttributeError):raise SearchError('api_error') from None
 hits,cached=(control or CONTROL).run(provider,key,query,request)
 return hits,cached,provider

"""Synthetic HTTP fixture. Not official programme data; never used in production."""
import json
from urllib.parse import urlparse,parse_qs
from services.web_search import ENDPOINT

URL='https://fixture.go.kr/program/swim'
HTML='''<html><main><script type="application/ld+json">{"@type":"SportsEvent","name":"테스트 전용 화곡 수영","startDate":"2099-01-05T14:00:00+09:00","endDate":"2099-12-05T15:00:00+09:00","location":{"name":"테스트 전용 센터","address":{"addressRegion":"서울","addressLocality":"강서구","streetAddress":"화곡동 테스트 주소"}},"organizer":{"name":"테스트 기관"}}</script><h1>테스트 전용 화곡 수영</h1><p>요일 및 시간: 월요일 오후 14:00~15:00</p><p>비용: 무료</p><p>대상: 60세 이상</p><p>문의 전화: 02-0000-0000</p><p>신청 방법: 공식 사이트 온라인 신청</p><p>접수 기간: 2099.01.01 ~ 2099.01.31</p><a href="/program/apply">신청하기</a></main></html>'''

class FakeTransport:
 def __init__(self,mode='ok',html=HTML):self.mode=mode;self.html=html;self.requests=[]
 def get(self,url,**kwargs):
  self.requests.append((url,kwargs))
  if url.startswith(ENDPOINT):
   query=parse_qs(urlparse(url).query).get('q',[''])[0]
   if self.mode=='quota' or '오류시험' in query:return 429,{},b'{"private":"not-for-user"}'
   if self.mode=='authentication':return 403,{},b'private'
   if self.mode=='bad_json':return 200,{},b'not json'
   if self.mode=='timeout':
    from services.web_search import SearchError
    raise SearchError('timeout')
   rows=[] if self.mode=='empty' or '부천' in query else [{'title':'테스트 검색','url':URL,'description':'환각 방지용 틀린 가격 999원'},{'title':'공식 미확인 테스트','url':'https://example.org/blog'}]
   return 200,{},json.dumps({'web':{'results':rows}}).encode()
  if self.mode=='page_error':return 503,{},b''
  if url.endswith('/program/apply'):return 200,{'content-type':'text/html; charset=utf-8'},b'<html>Public application route fixture</html>'
  return 200,{'content-type':'text/html; charset=utf-8'},self.html.encode()


class TavilyTransport(FakeTransport):
 def get(self,url,**kwargs):
  from services.search_providers import TAVILY_USAGE
  if url==TAVILY_USAGE:
   self.requests.append((url,kwargs))
   return 200,{},json.dumps({'key':{'usage':0,'limit':1000},'account':{'current_plan':'Researcher','plan_usage':0,'plan_limit':1000,'paygo_usage':0,'paygo_limit':0}}).encode()
  return super().get(url,**kwargs)
 def post(self,url,*,body,**kwargs):
  self.requests.append((url,dict(kwargs,body=body)))
  data=json.loads(body)
  from urllib.parse import urlencode
  status,headers,payload=super().get(ENDPOINT+'?'+urlencode({'q':data['query']}))
  self.requests.pop()  # internal fixture translation is not an outbound Brave request
  if status!=200:return status,headers,payload
  return 200,headers,json.dumps({'results':json.loads(payload)['web']['results'],'answer':'생성 답변은 절대 사용하지 않음'}).encode()

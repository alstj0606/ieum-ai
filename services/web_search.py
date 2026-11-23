"""Brave discovery + conservative public-page verification. No LLM-written facts.

Only HTTPS government hosts and hosts already grounded in the checked-in official
sources are trusted. Search snippets never become programme fields. Fetches have
bounded time/size, public DNS only, no cookies, no authentication and no form POST.
"""
from datetime import datetime, timezone, date
from zoneinfo import ZoneInfo
from html.parser import HTMLParser
from urllib.parse import urlparse, urlencode, urljoin, urldefrag
import hashlib
import ipaddress
import json
import re
import socket
import time

ENDPOINT='https://api.search.brave.com/res/v1/web/search'
ERRORS={'not_configured':'인터넷 검색이 아직 설정되지 않았어요. 저장 자료로 찾아볼 수 있어요.',
 'authentication':'검색 연결 설정을 확인해야 해요. 저장 자료로 계속 이용해 주세요.',
 'quota':'인터넷 검색 사용량이 잠시 초과됐어요. 잠시 뒤 다시 찾아주세요.',
 'timeout':'인터넷 검색이 오래 걸려요. 다시 시도해 주세요.',
 'api_error':'인터넷 검색에 연결하지 못했어요. 다시 시도해 주세요.',
 'page_error':'공식 페이지에 연결하지 못했어요. 잠시 뒤 다시 확인해 주세요.',
 'empty':'검색한 범위에서 확인할 수 있는 프로그램을 찾지 못했어요.',
 'unverified':'검색 자료는 있지만 프로그램의 공식 사실을 확인하지 못했어요.'}

class SearchError(Exception):
 def __init__(self,code):self.code=code if code in ERRORS else 'api_error';super().__init__(ERRORS[self.code])

class Transport:
 """Pinned public IP connection with TLS hostname verification (no DNS rebinding)."""
 def get(self,url,*,headers=None,timeout=6,max_bytes=1500000):
  import http.client,ssl
  parsed=urlparse(url)
  if parsed.scheme!='https' or parsed.username or parsed.password or parsed.port not in (None,443):raise SearchError('page_error')
  host=parsed.hostname or ''
  try:
   ips=list(dict.fromkeys(x[4][0] for x in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)))
   if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):raise SearchError('page_error')
   # TLS still validates/SNIs the original host, while the socket uses a checked IP.
   conn=http.client.HTTPSConnection(host,timeout=timeout,context=ssl.create_default_context())
   sock=socket.create_connection((ips[0],443),timeout=timeout)
   conn.sock=conn._context.wrap_socket(sock,server_hostname=host)
   path=parsed.path or '/'
   if parsed.query:path+='?'+parsed.query
   conn.request('GET',path,headers={'User-Agent':'IeumAI/1.0 (public programme information)',**(headers or {})})
   response=conn.getresponse();payload=response.read(max_bytes+1)
   if len(payload)>max_bytes:raise SearchError('page_error')
   return response.status,dict((k.lower(),v) for k,v in response.getheaders()),payload
  except (TimeoutError,socket.timeout):raise SearchError('timeout') from None
  except SearchError:raise
  except Exception:raise SearchError('page_error') from None
  finally:
   if 'conn' in locals():conn.close()


def official_hosts(rows):
 return {urlparse(r.get(k) or '').hostname for r in rows for k in ('source_url','official_url') if r.get(k)}-{None}

def safe_url(url):
 try:
  p=urlparse(url)
  if p.hostname in ('localhost','localhost.localdomain') or (p.hostname or '').endswith(('.local','.internal')):return False
  try:ipaddress.ip_address(p.hostname or '')
  except ValueError:pass
  else:return False
  return bool(len(url)<=2048 and p.scheme=='https' and p.hostname and not p.username and not p.password and p.port in (None,443) and not p.fragment and '\\' not in url and not re.search(r'[\x00-\x20]',url) and not any(k in p.query.lower() for k in ('password=','token=','authkey=','api_key=','apikey=')))
 except (ValueError,TypeError):return False

def is_official(url,hosts=()):
 if not safe_url(url):return False
 host=urlparse(url).hostname.lower()
 return host.endswith('.go.kr') or host in hosts

def fetch_page(url,hosts,transport,timeout=5):
 for _ in range(3):
  if not is_official(url,hosts) or re.search(r'(?:action=|/)(?:delete|logout|submit|save|insert|pay|checkout)(?:[&/?.=]|$)',url,re.I):raise SearchError('page_error')
  status,headers,body=transport.get(url,timeout=timeout)
  if status in (301,302,303,307,308):url=urljoin(url,headers.get('location',''));continue
  if status!=200:raise SearchError('page_error')
  if 'text/html' not in headers.get('content-type',''):raise SearchError('page_error')
  charset=re.search(r'charset=([\w-]+)',headers.get('content-type',''))
  try:text=body.decode(charset.group(1) if charset else 'utf-8')
  except (UnicodeError,LookupError):
   try:text=body.decode('cp949')
   except UnicodeError:raise SearchError('page_error') from None
  return url,text
 raise SearchError('page_error')

class Page(HTMLParser):
 def __init__(self):
  super().__init__(convert_charrefs=True);self.lines=[];self.links=[];self.structured=[];self.title=[];self.ignore=0;self.json_script=False;self.buffer='';self.anchor=None;self.heading=0
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='script' and a.get('type')=='application/ld+json':self.json_script=True;self.buffer=''
  if tag in ('script','style','nav','footer','header','noscript'):self.ignore+=1
  if tag in ('h1','h2') and not self.ignore:self.heading+=1
  if tag in ('p','div','li','tr','br','dt','dd','h1','h2'):self.lines.append('\n')
  if tag=='a' and not self.ignore:self.anchor=[a.get('href',''),'']
 def handle_endtag(self,tag):
  if tag=='script' and self.json_script:
   try:self.structured.append(json.loads(self.buffer))
   except (ValueError,TypeError):pass
   self.json_script=False
  if tag in ('script','style','nav','footer','header','noscript'):self.ignore=max(0,self.ignore-1)
  if tag in ('h1','h2'):self.heading=max(0,self.heading-1)
  if tag=='a' and self.anchor:self.links.append(self.anchor);self.anchor=None
  if tag in ('p','div','li','tr','dt','dd','h1','h2'):self.lines.append('\n')
 def handle_data(self,data):
  if self.json_script:self.buffer+=data
  if self.ignore:return
  if self.heading:self.title.append(data)
  self.lines.append(data+' ')
  if self.anchor:self.anchor[1]+=data
 def records(self):
  def walk(value):
   if isinstance(value,list):
    for v in value:yield from walk(v)
   elif isinstance(value,dict):
    kind=value.get('@type',[]);kind=[kind] if isinstance(kind,str) else kind if isinstance(kind,list) else []
    if any(x in kind for x in ('Event','SportsEvent','EducationEvent','CourseInstance','Course')):yield value
    if '@graph' in value:yield from walk(value['@graph'])
  return [r for value in self.structured for r in walk(value)]


def clean(value,limit=300):
 return re.sub(r'\s+',' ',value).strip()[:limit] if isinstance(value,str) else None

def phone_number(text):
 m=re.fullmatch(r'(?:\+82[ -]?)?0\d{1,2}-\d{3,4}-\d{4}',text or '')
 return text if m else None

def iso(value):
 if not isinstance(value,str) or not re.match(r'^\d{4}-\d{2}-\d{2}(?:T|$)',value):return None
 try:return datetime.fromisoformat(value).isoformat() if 'T' in value else date.fromisoformat(value).isoformat()
 except ValueError:return None

def recruitment_status(row,today=None):
 today=today or datetime.now(ZoneInfo('Asia/Seoul')).date()
 end=iso(row.get('registration_end'));start=iso(row.get('registration_start'));event_end=iso(row.get('ends_at'))
 if event_end and date.fromisoformat(event_end[:10])<today:return '운영 종료'
 if end and date.fromisoformat(end[:10])<today:return '접수 마감'
 # Dates alone cannot prove remaining seats/current enrollment or an undated status.
 status=row.get('registration_status_text') or ''
 if status in ('마감','접수 마감','모집 마감'):return '접수 마감'
 if start and date.fromisoformat(start[:10])>today:return '접수 예정'
 if (start and date.fromisoformat(start[:10])==today) or (end and date.fromisoformat(end[:10])==today):return '접수 시각 확인 필요'
 if start and end and date.fromisoformat(start[:10])<today<date.fromisoformat(end[:10]) and status in ('접수 중','모집 중','접수중','모집중'):return '접수 중 · 잔여석 확인 필요'
 return '모집 상태 확인 필요'

def extract_program(url,html,location,activity,checked_at,hosts,transport):
 page=Page();page.feed(html)
 records=page.records()
 # Multi-program pages are references, not a source for mixed-up card facts.
 if len(records)>1:return None
 lines=[clean(x) for x in ''.join(page.lines).splitlines() if clean(x)]
 text='\n'.join(lines)
 record=records[0] if records else {}
 def label(names):
  for i,line in enumerate(lines):
   m=re.match(r'^(?:'+names+r')(?:\s*[:：|]\s*|\s+)(.{1,280})$',line)
   if m:return clean(m.group(1))
   if re.fullmatch(names,line) and i+1<len(lines):return clean(lines[i+1])
  return None
 if not records and len([line for line in lines if re.match(r'^(?:프로그램명|강좌명|행사명)(?:[:：|\s]|$)',line)])>1:return None
 name=clean(record.get('name')) or label('프로그램명|강좌명|강좌 이름|행사명')
 if not name:return None
 place=record.get('location') or {};place=place if isinstance(place,dict) else {}
 address=place.get('address');address_string=clean(address);address=address if isinstance(address,dict) else {}
 address_text=address_string or ' '.join(clean(address.get(k)) or '' for k in ('addressRegion','addressLocality','streetAddress')).strip() or label('주소|상세 주소|장소 주소')
 facility=clean(place.get('name')) or label('장소|교육장소|운영 장소|교육 장소')
 # The searched region is never copied into the venue. Missing/mismatched venue is explicit.
 venue=' '.join(x for x in (address_text,facility) if x)
 city=location.get('city');area=location.get('district');dong=location.get('neighbourhood')
 relation='장소 지역 확인 필요'
 if venue:
  if area and area in venue and (not city or city in venue):relation='요청하신 구의 자료 · 동 일치 확인 필요'
  if dong and dong in venue and (not city or city in venue) and (not area or area in venue):relation='요청하신 동 이름이 주소에 표시됨 · 거리 미계산'
  elif city and city in venue and not area:relation='요청하신 시의 자료 · 거리 미계산'
  elif city and city not in venue:relation='요청 지역과 장소가 다르거나 지역 확인 필요'
  if area and area not in venue:relation='요청 지역과 장소가 다르거나 지역 확인 필요'
 if activity and activity not in name+' '+text:return None
 offer=record.get('offers') or {};offer=offer if isinstance(offer,dict) else {}
 fee=label('비용|수강료|참가비|참가 비용');amount=None;fee_unit=None
 if fee=='무료':amount=0
 elif fee and re.fullmatch(r'[\d,]+\s*원',fee):amount=int(re.sub(r'\D','',fee))
 if fee:
  unit_match=re.fullmatch(r'(월|회당|전체)\s*([\d,]+)\s*원',fee)
  if unit_match:fee_unit=unit_match.group(1);amount=int(unit_match.group(2).replace(',',''))
 if offer.get('priceCurrency')=='KRW' and re.fullmatch(r'\d+',str(offer.get('price',''))):
  structured_amount=int(offer['price'])
  if amount is not None and structured_amount!=amount:amount=None;fee='공식 페이지의 금액 표기가 달라 확인 필요'
  else:amount=structured_amount
 phone=label('문의 전화|문의전화|연락처|문의처|문의');phone=phone_number(phone)
 registration=label('접수 기간|모집 기간|신청 기간');registration_start=registration_end=None
 if registration:
  dates=re.findall(r'\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}',registration)
  if len(dates)==2:
   def normalize(d):
    y,m,day=map(int,re.split(r'[.\-/]',d))
    try:return date(y,m,day).isoformat()
    except ValueError:return None
   registration_start,registration_end=map(normalize,dates)
 links=[];attempts=0
 for href,label_text in page.links:
  target=urldefrag(urljoin(url,href))[0]
  if clean(label_text) in ('신청하기','수강신청','예약하기') and is_official(target,hosts) and urlparse(target).hostname==urlparse(url).hostname and target!=url:
   attempts+=1
   if attempts>2:break
   try:verified_url,_=fetch_page(target,hosts,transport,timeout=3)
   except SearchError:continue
   links.append((verified_url,'예약' if '예약' in label_text else '신청'));break
 organization=record.get('organizer') or {};organization=organization if isinstance(organization,dict) else {}
 result=dict(id='web-'+hashlib.sha256((url+'|'+name).encode()).hexdigest()[:16],name=name,
   institution=clean(organization.get('name')) or label('운영 기관|주최|운영기관'),facility=facility,address=clean(address_text),
   target=label('대상|참가 대상|모집 대상'),schedule=label('요일 및 시간|운영 시간|운영시간|교육 시간|수업 시간'),
   starts_at=iso(record.get('startDate')),ends_at=iso(record.get('endDate')),fee_amount=amount,fee_unit=fee_unit,fee_text=fee,
   registration_start=registration_start,registration_end=registration_end,registration_text=registration,registration_status_text=label('모집 상태|접수 상태|신청 상태'),
   registration_method=label('신청 방법|접수 방법|신청방법'),phone=phone,preparation=label('준비물|준비 사항'),
   official_url=url,application_url=links[0][0] if links else None,action=links[0][1] if links else None,
   match_label='활동명 직접 일치' if activity and activity in name else '검색 관련 자료 · 활동 종류 확인 필요',published_at=iso(record.get('datePublished')),verified_at=checked_at,source_kind='official_web',relation=relation,
   evidence={k:v for k,v in {'name':name,'phone':phone,'venue':clean(venue)}.items() if v})
 result['status']=recruitment_status(result)
 return validate_program(result)


def validate_program(row):
 if not isinstance(row,dict) or not clean(row.get('name')) or row.get('source_kind')!='official_web' or not safe_url(row.get('official_url')):raise SearchError('page_error')
 for key in ('phone',):
  if row.get(key) is not None and not phone_number(row[key]):raise SearchError('page_error')
 if row.get('application_url') and not safe_url(row['application_url']):raise SearchError('page_error')
 if row.get('fee_amount') is not None and (type(row['fee_amount']) is not int or not 0<=row['fee_amount']<=10000000):raise SearchError('page_error')
 for key in ('name','facility','address','target','schedule','registration_method','preparation','institution'):
  if row.get(key) is not None and (not isinstance(row[key],str) or len(row[key])>400):raise SearchError('page_error')
 return row


def search_programs(settings,location,conditions,*,transport=None,hosts=(),excluded=(),expanded=False):
 if not settings.search_api_key:raise SearchError('not_configured')
 transport=transport or Transport();started=time.monotonic()
 activity=conditions.get('activity_type') or {'체육':'운동','문화·취미':'문화 취미','평생학습':'교육'}.get(conditions.get('category'),'활동')
 # Only whitelisted short slots go to search, never raw utterances/history or age/medical data.
 parts=[location.get(k) for k in (('city','district') if expanded else ('city','district','neighbourhood')) if location.get(k)]
 if not parts:raise SearchError('empty')
 query=' '.join(parts+[activity,'프로그램 모집 공식'])
 if expanded:query+=' 인접 지역'
 if conditions.get('budget_amount')==0:query+=' 무료'
 checked_at=datetime.now(timezone.utc).isoformat(timespec='seconds')
 try:
  status,_,body=transport.get(ENDPOINT+'?'+urlencode({'q':query,'country':'KR','search_lang':'ko','count':8}),headers={'X-Subscription-Token':settings.search_api_key},timeout=8,max_bytes=1000000)
 except SearchError as error:raise SearchError('timeout' if error.code=='timeout' else 'api_error') from None
 if status in (401,403):raise SearchError('authentication')
 if status==429:raise SearchError('quota')
 if status!=200:raise SearchError('api_error')
 try:
  payload=json.loads(body);hits=payload.get('web',{}).get('results',[])
  if not isinstance(hits,list):raise ValueError()
 except (ValueError,TypeError,AttributeError):raise SearchError('api_error') from None
 rows=[];references=[];failures=0;seen=set();official_count=0
 for hit in sorted(hits[:8],key=lambda h:not is_official(h.get('url','') if isinstance(h,dict) else '',hosts)):
  if not isinstance(hit,dict):continue
  url=urldefrag(hit.get('url',''))[0] if isinstance(hit.get('url'),str) else ''
  if not safe_url(url) or url in seen:continue
  seen.add(url);official=is_official(url,hosts)
  ref=dict(title=clean(hit.get('title')) or '검색 자료',url=url,official=official,verified=False,published_at=clean(hit.get('age')),note='일반 검색 결과 · 공식 기관 미확인')
  if not official:references.append(ref);continue
  official_count+=1
  if official_count>5 or time.monotonic()-started>20:break
  try:
   final,html=fetch_page(url,hosts,transport);ref.update(url=final,verified=True,note='공식 페이지 · 프로그램 필드 확인 필요')
   row=extract_program(final,html,location,conditions.get('activity_type'),checked_at,hosts,transport)
   if row and row['id'] in excluded:continue
   if row:
    address=row['address'] or '';origin_dong=location.get('neighbourhood');address_dong=re.search(r'([가-힣]{2,10}\d{0,2}동)(?:\s|$|[)])',address)
    known_city=next((c for c in ('서울','부산','인천','대전','대구','광주','울산','창원','부천') if address.startswith(c)),None)
    address_area=re.search(r'([가-힣]{2,8}구)(?:\s|$)',address)
    if known_city and known_city!=location.get('city'):
     ref['note']='공식 자료 · 요청하신 시 밖의 프로그램';references.append(ref);continue
    mismatch=(address_area and location.get('district') and address_area.group(1)!=location['district']) or (address_dong and origin_dong and address_dong.group(1)!=origin_dong)
    if mismatch and not expanded:
     ref['note']='공식 자료 · 요청 지역 밖이거나 행정동·법정동 일치 확인 필요';references.append(ref);continue
    # Budget/time eligibility are not inferred. Unknowns stay explicit, known mismatch is omitted.
    if conditions.get('budget_amount') is not None and (row['fee_amount'] is None or row['fee_amount']>conditions['budget_amount']):
     ref['note']='공식 자료 · 비용 조건 일치 확인 필요';references.append(ref);continue
    target=row['target'] or '';age=conditions.get('age');minimum=re.search(r'(\d{1,3})세\s*이상',target);maximum=re.search(r'(\d{1,3})세\s*이하',target)
    if age is not None and ((minimum and age<int(minimum.group(1))) or (maximum and age>int(maximum.group(1)))):continue
    if conditions.get('gender')=='남성' and '여성' in target and '남성' not in target:continue
    if conditions.get('gender')=='여성' and '남성' in target and '여성' not in target:continue
    if conditions.get('budget_amount',0) and row['fee_amount'] and row['fee_unit']!=conditions.get('budget_unit'):
     ref['note']='공식 자료 · 비용의 회당·월 등 단위 확인 필요';references.append(ref);continue
    if conditions.get('time_slot') and conditions['time_slot'] not in (row['schedule'] or ''):
     ref['note']='공식 자료 · 희망 시간대 일치 확인 필요';references.append(ref);continue
    rows.append(row)
   else:references.append(ref)
  except (SearchError,ValueError,TypeError,KeyError,OverflowError,RecursionError):failures+=1;ref['note']='공식 사이트 접속·본문 확인 실패';references.append(ref)
 def rank(r):
  return (0 if r['match_label']=='활동명 직접 일치' else 1,0 if location.get('neighbourhood') and location['neighbourhood'] in (r['address'] or '') else 1,
          0 if r['status']=='모집 상태 확인 필요' else 1,r['name'])
 unique={}
 for row in sorted(rows,key=rank):unique.setdefault((row['name'],row['address'] or row['facility'] or row['official_url'],row['schedule'] or row['starts_at']),row)
 rows=list(unique.values())[:3]
 return dict(rows=rows,references=references[:6],checked_at=checked_at,status='ok' if rows else 'page_error' if official_count and failures==official_count else 'unverified' if references else 'empty',expanded=expanded)

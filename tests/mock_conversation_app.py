"""Local browser fixture: synthetic Gemini prose and Tavily pages, no real API calls."""
from pathlib import Path
import runpy,sys
sys.path.insert(0,str(Path(__file__).parent))
from web_fixture import TavilyTransport,HTML
from services.config import Settings
from services.ai import AIError
from services.dialogue import basic_extract
from services.conversation_ai import validate_plan
import services.config as config
import services.web_search as web_search
import services.search_providers as providers
import services.conversation_ai as conversation_ai

config.load_settings=lambda *a,**kw:Settings(tavily_api_key='synthetic-national-only',gemini_api_key='synthetic-conversation-only')
web_search.Transport=lambda:TavilyTransport('ok',HTML)
if not hasattr(providers,'_national_browser_control'):providers._national_browser_control=providers.SearchControl(minute_limit=1000,day_limit=1000,month_limit=1000)
providers.CONTROL=providers._national_browser_control

def hobby(name):return dict(name=name,reason='함께 배우며 이야기 나눌 수 있는 취미예요.',start='입문 방법부터 천천히 알아보세요.',materials='준비할 도구를 먼저 확인하세요.',cost_note='추가 구매 전에 확인하세요.')
def fixture(text,state,*a,**kw):
    if '연결실패' in text:raise AIError(code='timeout')
    extraction=basic_extract(text,state);route='search';answer='찾을 조건을 살펴볼게요.';items=[]
    if any(w in text for w in ('심심','추천','관심')):
        route='explore';answer='마음을 환기할 취미를 함께 골라봐요. 혼자 즐기거나 함께하는 쪽 중 무엇이 끌리세요?';items=[hobby('사진 일기'),hobby('합창')]
    if '사람' in text:
        route='explore';answer='함께 배우는 시간이 좋으시군요. 합창이나 춤은 어떠세요?';items=[hobby('댄스'),hobby('합창')]
    if '못' in text and '춤' in text:
        route='howto';answer='익숙하지 않아 걱정되시는군요. 입문 동작부터 천천히 익히는 방법도 있어요.';items=[hobby('댄스')]
    if '처음 배우면' in text:
        route='howto';answer='종이와 연필로 그리는 방법부터 천천히 익혀보세요.';items=[hobby('그림') ]
    if '돈 안 들고' in text:
        route='explore';answer='집에 있는 재료로 시작하는 취미도 있어요.';items=[hobby('종이 접기')]
    if '집에서' in text:
        route='home';answer='사진에 짧은 글을 붙여 일기를 만들어 보세요. 어떤 장면을 남기고 싶으세요?';items=[hobby('스마트폰 사진 일기')]
    return validate_plan(dict(extraction=extraction,route=route,reply=answer,idea_ids=[],hobbies=items))
conversation_ai.understand=fixture
runpy.run_path(str(Path(__file__).resolve().parents[1]/'app.py'),run_name='__main__')

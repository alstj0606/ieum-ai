"""Synthetic SDK HTTP integration for browser tests. No real keys or network."""
import json,runpy
from pathlib import Path
import httpx2
from google import genai
from services.ai import empty_extraction
from services.dialogue import new_state,basic_extract
from services.config import Settings
import services.config as config

config.load_settings=lambda *args,**kwargs:Settings(gemini_api_key='synthetic-sdk-browser-only')
if not hasattr(genai,'_ieum_original_client'):genai._ieum_original_client=genai.Client

def transport(request):
 context=json.loads(json.loads(request.content)['contents'][0]['parts'][0]['text']);text=context['utterance']
 state=new_state();state['conditions']=context.get('conditions',{})
 extraction=basic_extract(text,state);route='search' if '찾아' in text or '배우고 싶' in text else 'explore'
 answer='혼자 즐길 취미를 생각해 봐요. 무엇이 궁금하세요?'
 if '사람' in text:answer=('앞서 말씀하신 취미와 함께, 합창 같은 활동도 생각해 볼 수 있어요.' if context['conversation'] else '함께하는 활동을 생각해 봐요.')
 plan=dict(route=route,extraction=extraction,reply=answer,idea_ids=[],hobbies=[])
 return httpx2.Response(200,json={'candidates':[{'content':{'parts':[{'text':json.dumps(plan,ensure_ascii=False)}]},'finishReason':'STOP'}]})

def factory(**kwargs):
 options=kwargs['http_options'];http=httpx2.Client(transport=httpx2.MockTransport(transport),event_hooks=(options.client_args or {}).get('event_hooks'))
 kwargs['http_options']=options.model_copy(update={'httpx_client':http})
 return genai._ieum_original_client(**kwargs)
genai.Client=factory
runpy.run_path(str(Path(__file__).resolve().parents[1]/'app.py'),run_name='__main__')

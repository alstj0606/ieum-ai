"""Safe runtime evidence: identifiers/booleans/enums only, no messages or responses."""
from functools import lru_cache
from pathlib import Path
import hashlib
import re
import subprocess
from services.conversation_policy import phase

ROOT=Path(__file__).resolve().parents[1]
ENGINE='iphone-dialogue-v1'

@lru_cache(maxsize=1)
def build_identity():
    sha=None
    try:
        value=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,timeout=2,check=True).stdout.strip()
        if re.fullmatch('[0-9a-f]{40}',value):sha=value
    except (OSError,subprocess.SubprocessError):pass
    digest=hashlib.sha256()
    for name in ('app.py','gangseo_app.py','services/life_assistant.py','services/conversation_policy.py','services/conversation_ai.py','services/config.py','services/regions.py','ui/national_picker.py'):
        digest.update(name.encode());digest.update((ROOT/name).read_bytes())
    return {'commit':sha or '확인 불가','code_fingerprint':digest.hexdigest()[:16],'engine':ENGINE,'entrypoint':'app.py'}


def snapshot(state,settings):
    model=settings.model
    if not re.fullmatch(r'(?:models/)?gemini-[A-Za-z0-9._-]{1,80}',model or ''):model='설정 형식 확인 필요'
    return {**build_identity(),'gemini_key_configured':bool(settings.gemini_api_key),'model':model,
        'current_turn_ai':state.get('ai_call',{'attempted':False,'status':'not_attempted'}),'last_ai_call':state.get('last_ai_call'),
        'tavily_key_configured':bool(settings.tavily_api_key),'search_provider':settings.search_provider,
        'search_status':(state.get('search_failure') or {}).get('code') or state.get('web',{}).get('status','not_attempted'),
        'phase':phase(state),'route':state.get('conversation_route'),'pending':state.get('pending'),
        'loaded_modules_match_disk':loaded_modules_match_disk(),
        'gemini_reply_used':bool(state.get('gemini_reply_used')),'fallback':state.get('mode')=='fallback'}


def loaded_modules_match_disk():
    """Detect a live Python import cache that no longer matches checked-out source."""
    import importlib,types
    result={}
    for module_name,func_name in (('services.life_assistant','turn'),('services.life_assistant','_turn'),('services.neighbourhood','question')):
        try:
            module=importlib.import_module(module_name);function=getattr(module,func_name)
            loaded=function.__code__
            compiled=compile(Path(module.__file__).read_text(),loaded.co_filename,'exec',dont_inherit=True)
            code=next(c for c in compiled.co_consts if isinstance(c,types.CodeType) and c.co_name==func_name)
            result[module_name+'.'+func_name]=loaded==code
        except (OSError,AttributeError,SyntaxError,StopIteration):result[module_name+'.'+func_name]=None
    return result

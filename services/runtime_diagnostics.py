"""Safe execution evidence; no secrets, utterances, source or API bodies."""
from pathlib import Path
import hashlib
import re
import subprocess
from services.conversation_policy import phase

ROOT=Path(__file__).resolve().parents[1]
ENGINE='conversation-20261124'


def _git(*args):
    try:return subprocess.run(['git',*args],cwd=ROOT,capture_output=True,text=True,timeout=2,check=True).stdout.strip()
    except (OSError,subprocess.SubprocessError):return None


def build_identity():
    # Read current checkout at inspection time, not a cached pre-deploy value.
    sha=_git('rev-parse','HEAD');branch=_git('symbolic-ref','--short','HEAD')
    digest=hashlib.sha256()
    for name in ('app.py','gangseo_app.py','services/life_assistant.py','services/conversation_policy.py','services/conversation_ai.py','services/config.py','services/regions.py','ui/national_picker.py'):
        digest.update(name.encode());digest.update((ROOT/name).read_bytes())
    return {'commit':sha if re.fullmatch('[0-9a-f]{40}',sha or '') else '확인 불가',
            'checkout_branch':branch if re.fullmatch(r'[A-Za-z0-9._/-]{1,100}',branch or '') else '확인 불가',
            'code_fingerprint':digest.hexdigest()[:16],'diagnostics_revision':ENGINE}


def _repo_file(value):
    try:return Path(value).resolve().relative_to(ROOT).as_posix()
    except (TypeError,ValueError):return '확인 불가'


def execution_path(discovery=None,renderer=None):
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    from ui import national_picker
    context=get_script_run_ctx(suppress_warning=True)
    return {'entrypoint':_repo_file(context.main_script_path) if context else '확인 불가',
            'renderer':_repo_file(renderer),'discovery_enabled':discovery,
            'configured_handler':'services.life_assistant.turn' if discovery else 'services.dialogue.handle_turn' if discovery is False else '확인 불가',
            'picker_version':getattr(national_picker,'PICKER_VERSION','legacy_or_unknown'),
            'picker_module':_repo_file(national_picker.__file__)}


def snapshot(state,settings,*,discovery=None,renderer=None):
    model=settings.model
    if not re.fullmatch(r'(?:models/)?gemini-[A-Za-z0-9._-]{1,80}',model or ''):model='설정 형식 확인 필요'
    return {**build_identity(),**execution_path(discovery,renderer),
        'engine':state.get('engine_revision','not_observed'),'last_handler':state.get('last_handler','not_observed'),
        'gemini_key_configured':bool(settings.gemini_api_key),'model':model,
        'gemini_key_source':settings.gemini_key_source,'environment_key_present':settings.gemini_key_environment_present,
        'secrets_key_present':settings.gemini_key_secrets_present,'key_setting_conflict':settings.gemini_key_conflict,
        'model_source':settings.model_source,'model_setting_conflict':settings.model_setting_conflict,
        'current_turn_ai':state.get('ai_call',{'attempted':False,'status':'not_attempted'}),'last_ai_call':state.get('last_ai_call'),
        'tavily_key_configured':bool(settings.tavily_api_key),'search_provider':settings.search_provider,
        'search_status':(state.get('search_failure') or {}).get('code') or state.get('web',{}).get('status','not_attempted'),
        'phase':phase(state),'route':state.get('conversation_route'),'pending':state.get('pending'),
        'loaded_modules_match_disk':loaded_modules_match_disk(),
        'gemini_reply_used':bool(state.get('gemini_reply_used')),'fallback':state.get('mode')=='fallback'}


def loaded_modules_match_disk():
    """Compare loaded callable code to disk, including decorated picker callbacks."""
    import importlib,inspect,types
    result={}
    checks=(('services.life_assistant','turn'),('services.life_assistant','_turn'),
            ('services.discovery','discovery_turn'),('services.conversation_ai','understand'),
            ('services.conversation_policy','choose_route'),('services.neighbourhood','question'),
            ('ui.national_picker','render'),('ui.national_picker','choose'))
    for module_name,func_name in checks:
        try:
            module=importlib.import_module(module_name);function=inspect.unwrap(getattr(module,func_name))
            loaded=function.__code__
            compiled=compile(Path(module.__file__).read_text(),loaded.co_filename,'exec',dont_inherit=True)
            code=next(c for c in compiled.co_consts if isinstance(c,types.CodeType) and c.co_name==func_name)
            result[module_name+'.'+func_name]=loaded==code
        except (OSError,AttributeError,SyntaxError,StopIteration):result[module_name+'.'+func_name]=None
    return result

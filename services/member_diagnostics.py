"""Opt-in, session-only membership tracing. Never record text, secrets or provider data."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
from types import CodeType

REVISION='member-trace-1'
ENABLED='_member_diag_enabled'
TRACE='_member_diag_trace'
PHASES={'entry','before_action','after_action','render','post_render'}
SOURCES={'inst_start','inst_start_visual','inst_nonmember','inst_member','inst_unknown_member',
         'inst_has_id','inst_no_id','inst_reset','inst_previous','inst_next','inst_repeat','inst_stuck',
         'inst_membership','inst_programs','chat','other'}
ACTIONS={'reset','nonmember','member','unknown_member','member_with_id','member_without_id',
         'signup','previous','next','repeat','stuck','membership_help','program_info'}
SCREENS={'welcome','membership','membership_registration','membership_check','open_site','account',
         'menu','subject','result','signup_open','signup_menu','signup_id','signup_terms','signup_verify'}
ENUMS={'guide_kind':{'application','signup'},'view':{'welcome','guide','membership_registration','membership_check'},
       'member_type':{'unknown','nonmember','existing_member','existing_online','new_online'}}


def snapshot(value):
    value=value if isinstance(value,dict) else {}
    result={'present':bool(value)}
    for key in ('membership','online_account','active'):
        item=value.get(key);result[key]=item if item is None or type(item) is bool else 'invalid'
    for key,allowed in ENUMS.items():
        item=value.get(key);result[key]=item if isinstance(item,str) and item in allowed else None
    for key in ('index','seq'):
        item=value.get(key);result[key]=item if type(item) is int and 0<=item<=1000000 else None
    return result


def record(session,phase,*,action=None,source=None,screen=None):
    if not session.get(ENABLED) or phase not in PHASES:return
    number=session.get('_member_diag_event',0)+1
    session['_member_diag_event']=number
    event={'event':number,'run':session.get('_member_diag_run',0),'phase':phase,
           'state':snapshot(session.get('institution_session')),
           'visual_preference':session.get('inst_visual_preference') is True}
    if source is not None:event['source']=source if source in SOURCES else 'other'
    if action is not None:event['action']=action if action in ACTIONS else 'other'
    if screen is not None:event['screen']=screen if screen in SCREENS else 'other'
    session[TRACE]=(session.get(TRACE,[])+[event])[-24:]


def begin(session,enabled):
    session[ENABLED]=bool(enabled)
    if not enabled:
        # Disabling drops the transient report, without touching application state.
        for key in (TRACE,'_member_diag_run','_member_diag_event'):session.pop(key,None)
        return
    session['_member_diag_run']=session.get('_member_diag_run',0)+1
    record(session,'entry')


def function_matches_file(function,path):
    """Compare loaded code to the file without importing, executing or reloading it.

    Code equality includes nested functions/constants. inspect.getsource() alone
    reads disk and cannot establish which code a cached function is executing.
    """
    runtime=getattr(function,'__code__',None)
    if not isinstance(runtime,CodeType):return None
    try:
        compiled=compile(Path(path).read_text(encoding='utf-8'),str(path),'exec',dont_inherit=True)
        disk=next((c for c in compiled.co_consts if isinstance(c,CodeType) and c.co_name==runtime.co_name),None)
        return runtime==disk if disk is not None else None
    except (OSError,SyntaxError,UnicodeError):return None


def build_info(root,ui):
    root=Path(root);head=None;dirty=None
    try:
        git=subprocess.run(['git','rev-parse','HEAD'],cwd=root,capture_output=True,text=True,timeout=2)
        candidate=git.stdout.strip()
        if git.returncode==0 and re.fullmatch(r'[0-9a-f]{40,64}',candidate):
            head=candidate
            status=subprocess.run(['git','status','--porcelain','--untracked-files=no'],cwd=root,capture_output=True,text=True,timeout=2)
            if status.returncode==0:dirty=bool(status.stdout.strip())
    except (OSError,subprocess.TimeoutExpired):pass
    files={}
    for relative in ('app.py','ui/seongsan_app.py','services/institution_dialogue.py'):
        try:files[relative]=hashlib.sha256((root/relative).read_bytes()).hexdigest()[:12]
        except OSError:files[relative]=None
    checks={}
    for name,relative in [('render','ui/seongsan_app.py'),('_render_content','ui/seongsan_app.py'),
                          ('guide_turn','services/institution_dialogue.py'),('current_steps','services/institution_dialogue.py')]:
        checks[name]=function_matches_file(getattr(ui,name,None),root/relative)
    return {'diagnostic_version':REVISION,'working_tree_commit':head,'tracked_files_changed':dirty,
            'loaded_functions_match_files':checks,'file_hashes':files}


def report(session,root,ui):
    return {'build':build_info(root,ui),'current_state':snapshot(session.get('institution_session')),
            'trace':list(session.get(TRACE,[]))}


def render_panel(session,root,ui):
    if not session.get(ENABLED):return
    import streamlit as st
    with st.container(key='member_diagnostic_panel'):
        st.markdown('<style>.st-key-member_diagnostic_panel [data-testid="stCaptionContainer"] {opacity:1}.st-key-member_diagnostic_panel [data-testid="stCaptionContainer"] p {color:#334e68}</style>',unsafe_allow_html=True)
        with st.expander('임시 진단 · '+REVISION,expanded=True):
            st.caption('현재 세션의 단계만 기록해요. 발화·Secrets·음성·API 응답은 기록하지 않아요.')
            st.caption('working_tree_commit은 작업트리 HEAD예요. 실행 함수의 파일 일치 여부도 확인하세요. null=확인 불가. before_action → after_action → entry → render/post_render 순서예요.')
            st.code(json.dumps(report(session,root,ui),ensure_ascii=False,indent=2),language='json',wrap_lines=True)

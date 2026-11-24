"""Explicit two-turn production counselling test, using only fixed non-personal text."""
from dataclasses import replace
from services.config import normalize_model,ModelSettingError,GEMINI_API_BASE,GEMINI_API_VERSION
from services.dialogue import new_state

PROMPTS=('새로운 취미를 시작하고 싶은데 혼자 즐기는 편이 좋아요.',
         '집에 있는 물건으로 가볍게 시작하려면 어떻게 하면 될까요?')


def inspect_conversation(settings, *, client=None):
    from services.life_assistant import turn
    report={'key_present':bool(settings.gemini_api_key),'key_source':settings.gemini_key_source,
            'environment_key_present':settings.gemini_key_environment_present,'secrets_key_present':settings.gemini_key_secrets_present,
            'key_setting_conflict':settings.gemini_key_conflict,'model_setting_conflict':settings.model_setting_conflict,
            'model':None,'model_source':settings.model_source,'api_base':GEMINI_API_BASE,'api_version':GEMINI_API_VERSION,
            'http_status':None,'http_request_attempted':False,'http_response_received':False,
            'generation_success':False,'conversation_success':False,'connection_verified':False,'error_type':None,'turns':[],
            'context_forwarded':False,'quota_remaining':'not_verified'}
    try:report['model']=normalize_model(settings.model)
    except ModelSettingError:report['error_type']='model_config';return report
    if not settings.gemini_api_key:report['error_type']='key_missing';return report
    # This test never starts a web search, spends Tavily quota, or reads real history.
    probe_settings=replace(settings,tavily_api_key='',search_api_key='',search_provider='tavily',allow_paid_search=False)
    state=dict(new_state(),life_mode=True,web_enabled=True)
    for prompt in PROMPTS:
        context_exists=bool(state.get('history'))
        state,_=turn(state,prompt,[],probe_settings,client=client)
        trace=state.get('ai_call',{})
        item={key:trace.get(key) for key in ('http_request_attempted','http_response_received','http_status','generation_succeeded','json_parsed','validated','stage')}
        item.update(error_type=trace.get('error'),reply_used=bool(state.get('gemini_reply_used')),fallback=state.get('mode')=='fallback')
        if item['error_type'] is None and not item['reply_used']:item['error_type']='reply_not_used'
        report['turns'].append(item)
        report.update(http_status=item['http_status'],http_request_attempted=bool(item['http_request_attempted']),
                      http_response_received=bool(item['http_response_received']),error_type=item['error_type'])
        if context_exists and item['http_request_attempted']:report['context_forwarded']=True
        if not item['reply_used']:break
    report['generation_success']=bool(report['turns']) and all(x['generation_succeeded'] for x in report['turns'])
    report['conversation_success']=len(report['turns'])==2 and all(x['reply_used'] and not x['fallback'] for x in report['turns'])
    report['connection_verified']=report['conversation_success'] and all(x['http_response_received'] and type(x['http_status']) is int and 200<=x['http_status']<300 for x in report['turns'])
    return report

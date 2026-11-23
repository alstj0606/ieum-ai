"""One Gemini request for conversational routing and grounded slots, never programme facts."""
import json
import re
from copy import deepcopy
from services.ai import (SCHEMA, PROMPT, AIError, make_client, generation_text,
                         validate_extraction)
from services.config import normalize_model, ModelSettingError
from services.diagnostics import classify_error
from services.activity_guidance import IDEAS

ROUTES = ('explore', 'howto', 'home', 'search', 'chat', 'followup')
# Conversational phrasing is an approved vocabulary, not a second facts channel.
REPLIES = ('', '새로운 즐거움을 함께 찾아봐요.',
    '사람들과 함께 즐길 활동을 생각해 볼 수 있어요.',
    '그리거나 가꾸는 취미를 생각해 볼 수 있어요.',
    '집에서 시작할 수 있는 취미부터 골라봐요.',
    '처음에는 연필과 종이로 주변 물건 하나를 천천히 그려보세요.',
    '처음에는 필요한 도구와 입문 방법부터 살펴보면 좋아요.',
    '원하시는 분위기에 맞춰 다른 활동도 살펴볼게요.',
    '움직이는 활동이 끌리시는군요. 원하시는 방식부터 골라봐요.')
SCHEMA_TURN = {'type':'object','additionalProperties':False,'properties':{
    'extraction':deepcopy(SCHEMA),
    'route':{'type':'string','enum':list(ROUTES)},
    'idea_ids':{'type':'array','items':{'type':'string','enum':[x['id'] for x in IDEAS]},'maxItems':3},
    'reply':{'type':'string','enum':list(REPLIES)}},
    'required':['extraction','route','idea_ids','reply']}
INSTRUCTION = PROMPT + """
추가 역할: 사용자와 취미·생활 활동을 탐색한다. extraction은 기존 규칙 그대로다.
route: explore=막연한 심심함/관심 탐색, howto=활동 시작 방법 상담,
home=집에서 하는 취미, search=실제 시설/강좌 찾기(배우고 싶다는 뜻 포함),
chat=인사/감사, followup=조건 수정/거절/이전 추천 후속 요청.
이전 대화와 현재 의도를 보고 판단하라. 상담만 원하면 검색하지 않는다.
idea_ids는 제공된 일반 활동 중 관심에 맞는 것만 최대 세 개 고른다.
reply는 일반적인 공감·취미 제안·시작 요령만 쉬운 한국어 한두 문장으로 쓴다.
질문은 서버가 결정한다. 물음표나 추가 질문을 reply에 넣지 마라.
시설/기관/실제 프로그램 이름, 장소, 일정, 가격, 번호, URL, 모집/예약/완료 주장,
운동 효과나 개인의 의학적 적합성은 reply에 절대 넣지 마라.
주어진 활동 아이디어 밖의 고유명사나 사실을 생성하지 마라. reply는 제공된 approved_replies 중 문맥에 맞는 문장만 그대로 선택한다. 애매하면 빈 문자열.
검색 결과와 실제 신청 정보는 별도 코드가 검증된 출처에서만 표시한다.
"""


def validate_plan(payload):
    if not isinstance(payload,dict) or set(payload)!=set(SCHEMA_TURN['required']):raise AIError(code='response_format')
    validate_extraction(payload['extraction'])
    if payload['route'] not in ROUTES:raise AIError(code='response_format')
    ids=payload['idea_ids'];allowed={x['id'] for x in IDEAS}
    if not isinstance(ids,list) or len(ids)>3 or any(not isinstance(x,str) or x not in allowed for x in ids) or len(set(ids))!=len(ids):raise AIError(code='response_format')
    reply=payload['reply']
    if not isinstance(reply,str) or reply not in REPLIES:raise AIError(code='response_format')
    # Fail closed: model prose never becomes a source of actionable programme facts.
    if re.search(r'\d|https?|www\.|[<>\[\]{}?？]|전화|주소|센터|복지관|시설|강좌|프로그램|모집|접수|예약|신청|결제|완료|운영|무료|원(?:이에요|입니다)|치료|예방|완치|효과|안전해|서울|강서|부천|인천|[가-힣]+(?:시에서|구에서|동에서)',reply,re.I):
        raise AIError(code='response_format')
    if len(re.findall(r'[.!。]',reply))>3:raise AIError(code='response_format')
    return payload


def understand(text,state,activities,settings,*,client=None):
    if not text.strip() or len(text)>1500:raise AIError(code='response_format')
    try:model=normalize_model(settings.model)
    except ModelSettingError:raise AIError(code='model_config') from None
    owned=client is None;client=client or make_client(settings)
    try:
        from google.genai import types
        context={'utterance':text,'conditions':state.get('conditions',{}),'pending':state.get('pending'),
                 'conversation':state.get('history',[])[-8:], 'last_route':state.get('conversation_route'),
                 'activity_ideas':[{k:x[k] for k in ('id','name','reason')} for x in IDEAS], 'approved_replies':REPLIES}
        response=client.models.generate_content(model=model,contents=json.dumps(context,ensure_ascii=False),
            config=types.GenerateContentConfig(system_instruction=INSTRUCTION,response_mime_type='application/json',
                response_json_schema=SCHEMA_TURN,max_output_tokens=2500,temperature=0,
                thinking_config=types.ThinkingConfig(thinking_budget=0) if model=='gemini-2.5-flash' else None,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)))
        return validate_plan(json.loads(generation_text(response)))
    except AIError:raise
    except (ValueError,TypeError):raise AIError(code='response_format') from None
    except Exception as error:raise AIError(code=classify_error(error)) from None
    finally:
        if owned:
            try:client.close()
            except Exception:pass

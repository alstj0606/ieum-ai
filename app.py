"""어르신을 위한 하나의 대화창. 사실은 공식 JSON, AI는 조건만 이해한다."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path
import re

import streamlit as st

from services.activities import load_activities
from services.config import load_settings
from services.diagnostics import DIAGNOSTICS
from services.model_probe import inspect_models, STATUS_LABELS
from services.generation_probe import inspect_generation, COMPARISON_LABELS
from services.dialogue import new_state, handle_turn, manual_search, application_guide, basic_extract, choose_idea, choose_alternative
from services.recommendations import activity_facts, speech_text
from services.voice import transcribe, synthesize, VoiceError

ROOT = Path(__file__).parent
st.set_page_config(page_title="이음 AI · 활동 찾기", page_icon="💬")
st.markdown(f"<style>{(ROOT/'ui/chat.css').read_text()}</style>", unsafe_allow_html=True)
try:
    secrets = dict(st.secrets)
except Exception:
    secrets = {}  # Never display secret parser errors.
settings = load_settings(secrets)
del secrets
try:
    activities = load_activities()
except (OSError, ValueError):
    activities = []
    st.error("공식 자료를 읽지 못했어요. 잠시 후 다시 찾아주세요.")
for key, value in {"dialog":new_state(), "turns":[], "speech":None, "auto_read":None,
                   "close_menu":False, "turn_seq":0, "speech_error":None, "voice_error":None, "transcript":None, "upload_seen":None, "edit_voice":False}.items():
    if key not in st.session_state:
        st.session_state[key] = value


def remember(text, state, *, voice=False, preserve=False):
    if not preserve:
        st.session_state.dialog = state
    st.session_state.turn_seq += 1
    st.session_state.speech = None
    st.session_state.speech_error = None
    st.session_state.turns.append({"user":text,"state":deepcopy(state)})
    st.session_state.turns = st.session_state.turns[-20:]
    st.session_state.auto_read = len(st.session_state.turns)-1 if voice and not state["error"] else None


def send(text, *, voice=False, fixed=False):
    st.session_state.voice_error = None
    state = st.session_state.dialog
    compact = text.replace(" ", "").rstrip(".!?")
    if compact in {"다시말해줘", "다시들려줘", "천천히알려줘", "천천히말해줘"} and state["code"] != "start":
        state = deepcopy(state)
        state["history"] += [{"role":"user","content":text}, {"role":"assistant","content":state["message"]}]
        state["history"] = state["history"][-20:]
        # The exact verified answer is repeated; slow mode changes only synthesis speed.
        state["slow_read"] = "천천히" in compact
        remember(text, state, voice=True)
    else:
        state = handle_turn(state, text, activities, settings,
                            extraction=basic_extract(text, state) if fixed else None)
        remember(text, state, voice=voice)


def select_idea(idea_id):
    state=st.session_state.dialog
    updated=choose_idea(state,idea_id,activities,settings)
    name=next(row['name'] for row in state['ideas'] if row['id']==idea_id)
    remember(name+' 프로그램을 찾아주세요',updated)


def select_alternative(activity_type):
    updated=choose_alternative(st.session_state.dialog,activity_type,activities,settings)
    remember(activity_type+' 대안 프로그램을 볼게요',updated)
    st.session_state.turns[-1]['detail_first']=True


def submit_voice(audio):
    st.session_state.voice_error = None
    try:
        with st.spinner("말씀을 알아듣고 있어요…"):
            text = transcribe(audio.getvalue(), settings, filename=audio.name)
        st.session_state.transcript = text
        st.session_state.edit_voice = False
        send(text, voice=True)
    except VoiceError as error:
        st.session_state.voice_error = str(error)


def edit_transcript():
    # Callback runs before widgets: each recording starts with its own transcript.
    st.session_state.corrected = st.session_state.transcript
    st.session_state.edit_voice = True


def reset():
    st.session_state.close_menu = True
    st.session_state.dialog = new_state()
    st.session_state.turns = []
    st.session_state.speech = None
    st.session_state.transcript = None
    st.session_state.voice_error = None
    st.session_state.upload_seen = None


def apply(activity_id):
    state = application_guide(st.session_state.dialog, activities, selected_id=activity_id)
    remember("이 활동 신청 방법을 알려주세요", state)


def prepare(index):
    turn = st.session_state.turns[index]
    state = turn["state"]
    st.session_state.speech_error = None
    rows = state["results"] or state["references"]
    if state["selected_id"]:
        rows = [row for row in rows if row["id"] == state["selected_id"]]
    spoken = speech_text("선택하신 프로그램 정보예요." if turn.get("detail_first") and rows else state["message"], rows)
    if state.get('alternatives') and not turn.get('detail_first'):
        spoken+=' 같은 지역의 공식 자료가 있는 대안이에요. '+ ' '.join(x['activity_type']+'. '+x['reason']+' '.join(row['name']+'. '+dict(activity_facts(row))['접수 상태'] for row in x['rows']) for x in state['alternatives'])
    if state.get('ideas') and not turn.get('detail_first'):
        spoken+=' 일반 활동 제안이며 실제 모집 강좌가 아니에요. '+ ' '.join(x['name']+'. '+x['reason'] for x in state['ideas'])
    if state.get('facilities'):
        spoken+=' '.join(x['name']+'. '+x['note'] for x in state['facilities'])
    if state.get("notice"):
        spoken = state["notice"] + " " + spoken
    try:
        with st.spinner("음성 안내를 준비하고 있어요…"):
            data = synthesize(spoken, settings, speed=0.7 if state.get("slow_read") else 0.9)
        st.session_state.speech = {"index":index,"data":data,"text":spoken,"autoplay":True}
    except VoiceError as error:
        st.session_state.speech = None
        st.session_state.speech_error = (index, str(error))


def card(row, index, position, *, reference=False, latest=False):
    facts = dict(activity_facts(row))
    with st.container(border=True):
        st.subheader(row["name"])
        # Status follows the title; essential information never needs an expander.
        st.markdown('**접수 상태 · '+facts['접수 상태']+'**')
        if reference:
            st.warning('참고 자료예요. 지금 신청 가능하다고 확인된 활동은 아니에요.')
        for label,key in (("참가 비용","비용"),("모집 대상","대상"),("지역","지역"),
                          ("장소","장소"),("상세 주소","주소"),("운영 시간","일정"),
                          ("접수 기간","접수 기간"),("다음 접수 예정일","다음 접수 예정일"),
                          ("신청 방법","신청 방법"),("준비물","준비물")):
            value=facts[key].replace("~", r"\~")
            st.markdown(f"{label}  \n**{value}**")
        with st.expander("주의사항·공식 출처"):
            for label in ("정보 확인일","접수 시각","접수 참고","비용 참고"):
                st.write(f"**{label}** · {facts[label]}")
            for note in row.get("condition_notes", []) + row.get("verification_notes", []):
                st.write(note)
            st.link_button("공식 출처 확인",row["source_url"],use_container_width=True)
            if row["official_url"]:
                st.link_button("공식 안내·신청 페이지 열기",row["official_url"],use_container_width=True)
            # Only phone strings literally present in the verified record are linkified.
            phones = sorted(set(re.findall(r"(?<!\d)0\d{1,2}-\d{3,4}-\d{4}(?!\d)",row.get("registration_method") or "")))
            for phone in phones:
                st.markdown(f"[📞 {phone} 전화하기](tel:{phone.replace('-', '')})")
            if latest and not reference:
                st.button("이 활동 신청 방법",key=f"apply_{row['id']}",on_click=apply,args=(row["id"],),use_container_width=True)


st.title("이음 AI")
if not st.session_state.turns:
    with st.chat_message("assistant"):
        st.write("안녕하세요. 어떤 활동을 하고 싶으세요? 글로 적거나 마이크를 눌러 말씀해 주세요.")
        if not settings.gemini_api_key:
            st.caption("Gemini 질문 이해가 미설정되어 기본 규칙으로 안내해요.")
        st.caption("질문 이해: Gemini · 음성 입력·안내: OpenAI(별도 키와 사용량 필요).")

with st.popover("＋ 보조 메뉴", use_container_width=False):
    with st.expander("AI 도움 없이 찾아보기"):
        with st.form("manual_form"):
            category=st.selectbox("활동 분류",["전체","체육","문화·취미","평생학습"],key="manual_category")
            slot=st.selectbox("편한 시간",["상관없음","오전","오후","저녁"],key="manual_time")
            if st.form_submit_button("선택한 조건으로 찾기",key="manual_submit"):
                st.session_state.close_menu = True
                state=manual_search(st.session_state.dialog,activities,category=None if category=="전체" else category,
                                    time_slot=None if slot=="상관없음" else slot)
                remember("선택한 조건으로 찾아주세요",state)
                st.rerun()
    with st.expander("음성파일 올리기"):
        st.caption("파일 선택 후 OpenAI로 보내 자동 검색해요. WAV는 1분, 모든 파일은 5MB 이내예요.")
        uploaded=st.file_uploader("음성파일 선택",type=["wav","m4a","mp3","webm"],key="voice_upload",disabled=not bool(settings.api_key))
        if uploaded is not None:
            token=hashlib.sha256(uploaded.getvalue()).hexdigest()
            if token != st.session_state.upload_seen:
                st.session_state.upload_seen=token
                st.session_state.close_menu = True
                submit_voice(uploaded)
    with st.expander("예시 체험 · 가상 수영 프로그램"):
        if st.button("초보 수영 찾기",key="demo_example"):
            st.session_state.close_menu = True
            demo=json.loads((ROOT/"data/demo_program.json").read_text())
            state=new_state()
            state.update(message="시연용 데이터 · 가상 프로그램 · 실제 신청 불가",code="demo",demo=demo)
            remember("초보 수영 예시 체험",state,preserve=True)
            st.rerun()
    with st.expander("자료와 이용 안내"):
        st.write(f"서울 강서구 공식 자료 {len(activities)}건이며 실시간 접수 정보는 아니에요.")
        st.write("녹음 종료 후 OpenAI로 음성을 보내 글로 바꾸고 검색해요. 조용해져도 자동 종료하지 않아요. 1분 이내로 말씀해 주세요.")
        st.write("Gemini는 조건만 이해해요. 음성 입력·안내는 기존 OpenAI API이며 Gemini 무료 한도와 별개예요. 실제 신청·예약·결제는 하지 않아요.")
        st.write("마이크 권한을 허용하고 HTTPS 주소를 직접 열어주세요. 마이크가 안 되면 글로 계속 질문할 수 있어요.")
    with st.expander("연결 상태 확인"):
        diagnostic=st.session_state.dialog.get('diagnostic')
        if diagnostic:
            code=diagnostic['code']
            st.write(f"진단 코드: {code}")
            st.write(DIAGNOSTICS.get(code,DIAGNOSTICS['unknown']))
        else:st.write("현재 대화에 기록된 연결 오류가 없어요.")
    with st.expander("Gemini 모델 연결 점검"):
        st.write("읽기 전용 모델 정보·목록을 조회해요. 질문·음성은 전송하지 않으며 생성 요청은 하지 않아요. 목록에 있어도 무료 이용이나 생성 성공을 보장하지 않아요.")
        if st.button("모델 정보 확인",key="inspect_models",disabled=not bool(settings.gemini_api_key)):
            with st.spinner("모델 정보를 확인하고 있어요…"):
                st.session_state.model_report = inspect_models(settings)
        if "model_report" in st.session_state:
            report = st.session_state.model_report
            st.write("모델: " + (report["model"] or "설정 형식 확인 필요"))
            st.write("설정 출처: " + report["model_source"])
            st.write("공식 API: " + report["api_base"] + "/" + report["api_version"])
            if report["model_setting"] == "model_config":
                st.warning(DIAGNOSTICS["model_config"])
            for label, key in (("모델 정보", "metadata_code"),("모델 목록", "list_code")):
                code = report[key]
                st.write(f"{label}: {code}")
                st.write(STATUS_LABELS.get(code, DIAGNOSTICS.get(code,"확인 필요")))
            if report["custom_base_ignored"]:
                st.write("대체 서버 주소 환경변수가 있지만 이 앱은 공식 주소로 고정해 사용해요. 환경변수 값은 표시하지 않아요.")
            if report["models"]:
                st.write("첫 페이지에서 generateContent 지원이 표시된 Gemini 모델 ID예요. 자동으로 선택하거나 전환하지 않아요.")
                st.code("\n".join(report["models"]),language=None)
            st.write("무료 티어·잔여 한도는 미확인입니다. AI Studio에서 같은 프로젝트의 모델별 한도를 확인해 주세요.")
    with st.expander("Gemini 생성 요청 점검"):
        st.write("선택 점검이에요. 설정된 모델로 고정 인사말을 보내고, 성공하면 같은 고정 문장을 기존 구조화 추출로 한 번 더 보내요. 최대 두 번 생성하며 API 사용량이 발생해요. 실제 대화·음성은 보내지 않고 응답 원문은 표시하지 않아요.")
        if st.button("고정 인사말로 생성 점검",key="inspect_generation",disabled=not bool(settings.gemini_api_key)):
            with st.spinner("고정 문장으로 생성 요청을 비교하고 있어요…"):
                st.session_state.generation_report = inspect_generation(settings, activities)
        if "generation_report" in st.session_state:
            probe = st.session_state.generation_report
            st.write("점검 모델: " + (probe["model"] or "설정 형식 확인 필요"))
            if probe["path"]:
                st.write("요청 대상: POST " + probe["api_base"] + probe["path"])
            for label, field in (("단순 생성", "simple_code"),("구조화 추출", "structured_code")):
                code = probe[field]
                st.write(f"{label}: {code}")
                if code not in ("ok", "not_run"):
                    st.write(DIAGNOSTICS.get(code, DIAGNOSTICS["unknown"]))
            st.write(COMPARISON_LABELS[probe["comparison"]])
            st.caption("고정 문장 점검은 무료 자격·남은 한도나 실제 사용자 질문의 정상 동작을 보장하지 않아요.")
    st.button("처음부터 다시 찾기",key="reset",on_click=reset)

for index, turn in enumerate(st.session_state.turns):
    latest=index==len(st.session_state.turns)-1
    state=turn["state"]
    with st.chat_message("user"):
        st.write(turn["user"])
    with st.chat_message("assistant"):
        if latest:
            st.markdown(f'<div id="latest-reply-{st.session_state.turn_seq}"></div>',unsafe_allow_html=True)
        if state["error"]:
            st.warning(state["error"])
        else:
            detail_first=bool(turn.get('detail_first') and (state['results'] or state['references']))
            rows=list({row['id']:row for row in (state['results'] or state['references'])}.values())[:3]
            if detail_first:
                for position,row in enumerate(rows):
                    card(row,index,position,reference=not bool(state['results']),latest=latest)
            if state.get("notice"):
                st.info(state["notice"])
            if not detail_first:
                st.write(state["message"])
            if state.get('alternatives') and not detail_first:
                st.markdown('**같은 지역의 대안 · 공식 자료 있음**')
                for option in state['alternatives']:
                    st.write(option['reason'])
                    for candidate in option['rows']:
                        facts=dict(activity_facts(candidate))
                        st.write(candidate['name']+' · '+facts['접수 상태'])
                    if latest:
                        st.button(option['activity_type']+' 정보 보기 →',key='alternative_'+option['activity_type'],
                                  on_click=select_alternative,args=(option['activity_type'],),use_container_width=True,type='primary')
            if state["code"]=="demo":
                demo=state["demo"]
                st.subheader(demo["name"])
                for label,key in (("대상","audience"),("시간","schedule"),("비용","fee"),("접수 기간","registration_period")):
                    st.write(f"**{label}** · {demo[key]}")
            elif not detail_first:
                for position,row in enumerate(rows):
                    card(row,index,position,reference=not bool(state["results"]),latest=latest)
            if state.get('facilities'):
                for facility in state['facilities']:
                    with st.container(border=True):
                        st.subheader(facility['name'])
                        st.write('공식 프로그램 자료에 등장하는 시설 · 현재 이용 가능 여부 미확인')
                        st.write('주소: '+(facility['address'] or '확인 필요'))
                        st.write('확인일: '+facility['verified_at'])
                        st.write('근거 프로그램: '+facility['source_program'])
                        st.write('근거 프로그램 접수 상태: '+facility['source_status'])
                        st.write(facility['note'])
                        st.link_button('시설 근거 공식 출처',facility['source_url'],use_container_width=True)
            if state.get('ideas') and not detail_first:
                st.markdown('**일반 활동 제안 · 실제 모집 프로그램 아님**')
                for idea in state['ideas']:
                    st.write('**'+idea['name']+'** · '+idea['reason'])
                    if latest:
                        st.button(idea['name']+' 알아보기',key='idea_'+idea['id'],on_click=select_idea,
                                  args=(idea['id'],),use_container_width=True)
            if latest and state.get('ideas') and not state['results'] and not detail_first:
                with st.expander('공식 페이지에서 직접 더 찾아보기'):
                    st.write('실시간 검색 결과가 아니에요. 보유 자료의 공식 페이지를 열어 기관의 다른 공고를 직접 확인해 주세요.')
                    seen=set()
                    for source in activities:
                        from urllib.parse import urlsplit
                        host=urlsplit(source['source_url']).hostname
                        if host in seen:continue
                        seen.add(host)
                        st.link_button('공식 자료 · '+source['facility_name'],source['source_url'],use_container_width=True)
                        if len(seen)==3:break
            if latest and state.get('ideas') and state['conditions'].get('time_slot'):
                st.button('시간 조건 풀기',key='relax_time',on_click=send,args=('시간은 상관없어요',),kwargs={'fixed':True},use_container_width=True)
            if latest and state['code']=='unsupported_region':
                st.button('서울 강서구 자료로 찾기',key='supported_region',on_click=send,args=('서울 강서구요',),kwargs={'fixed':True},use_container_width=True)
            if latest and state["code"] not in {"demo","start"}:
                if state['pending']=='expand_region':
                    st.button('네, 인접 지역도 확인',key='expand_yes',on_click=send,args=('인접 지역도 확인',),kwargs={'fixed':True},use_container_width=True)
                    st.button('아니요, 이 지역만 볼게요',key='expand_no',on_click=send,args=('이 지역만 볼게요',),kwargs={'fixed':True},use_container_width=True)
                elif state["pending"]=="region":
                    st.button("서울 강서구에서 찾기",key="choose_region",on_click=send,args=("서울 강서구요",),kwargs={"fixed":True},use_container_width=True)
                elif state["pending"]=="time_slot":
                    for name in ("오전","오후","저녁","상관없어요"):
                        st.button(name,key=f"time_{name}",on_click=send,args=(name,),kwargs={"fixed":True},use_container_width=True)
                elif state["pending"]=="budget_unit":
                    for name in ("한 번 금액이에요","한 달 금액이에요"):
                        st.button(name,key=f"budget_{name}",on_click=send,args=(name,),kwargs={"fixed":True})
                else:
                    st.button("다른 활동 찾기",key="change_activity",on_click=send,args=("다른 활동",),kwargs={"fixed":True})
                    st.button("다른 시간 찾기",key="change_time",on_click=send,args=("다른 시간",),kwargs={"fixed":True})
            if state["code"] != "demo":
                if st.session_state.auto_read==index:
                    st.session_state.auto_read=None
                    prepare(index)
                if st.session_state.speech_error and st.session_state.speech_error[0]==index:
                    st.warning(st.session_state.speech_error[1])
                speech=st.session_state.speech
                if not speech or speech["index"]!=index:
                    if st.button("답변 듣기",key=f"listen_{index}",disabled=not bool(settings.api_key),use_container_width=True):
                        prepare(index)
                        st.rerun()
                else:
                    with st.expander("음성으로 읽는 내용"):
                        st.text(speech["text"])
                    st.caption("AI가 만든 음성이에요. 소리가 안 나면 답변 듣기를 누르세요.")
                    st.audio(speech["data"],format="audio/mp3",autoplay=speech["autoplay"])
                    speech["autoplay"]=False
                    st.html((ROOT/"ui/player.html").read_text(),unsafe_allow_javascript=True)
                    if st.button("음성 중지",key="stop_speech",use_container_width=True):
                        st.session_state.speech=None
                        st.rerun()

if st.session_state.voice_error:
    st.warning(st.session_state.voice_error)
    st.write("아래 입력창에서 글로 질문하거나 마이크로 다시 말씀해 주세요.")
if st.session_state.transcript or st.session_state.voice_error:
    st.html("""<button id="ieum-retry-voice" type="button" aria-label="다시 말하기"
      style="width:100%;min-height:64px;font-size:20px;border:2px solid #1671c5;
      border-radius:12px;background:#eaf4ff;color:#102f50">🎤 다시 말하기</button>
      <p id="ieum-retry-status" role="status" aria-live="polite" style="font-size:20px;color:#384454"></p>""")
if st.session_state.transcript:
    with st.expander("음성인식이 다르게 되었나요?"):
        st.write(st.session_state.transcript)
        st.button("글자 수정하기",key="edit_transcript",on_click=edit_transcript)
        if st.session_state.edit_voice:
            corrected=st.text_area("인식된 문장 수정",key="corrected")
            if st.button("고친 질문 보내기",key="submit_correction"):
                send(corrected)
                st.session_state.edit_voice=False
                st.rerun()
        st.caption("다시 말하려면 아래 입력창의 마이크를 누르세요. 조건을 모두 바꾸려면 보조 메뉴에서 처음부터 다시 찾으세요.")

# Native pinned composer supports audio submit on stop and text submit without two forms.
request=st.chat_input("질문을 적어주세요",key="chat",accept_audio=True,max_chars=1500)
if request:
    if getattr(request,"audio",None) is not None:
        submit_voice(request.audio)
    else:
        send(request if isinstance(request,str) else request.text)
    st.rerun()
st.html(f'<script>{(ROOT/"ui/chat.js").read_text()}</script>',unsafe_allow_javascript=True)
if st.session_state.close_menu:
    st.session_state.close_menu = False
    st.html("<script>document.querySelector('[data-testid=stPopoverButton][aria-expanded=true]')?.click();</script>",unsafe_allow_javascript=True)
if st.session_state.turns:
    seq=st.session_state.turn_seq
    detail_scroll="true" if st.session_state.turns[-1].get('detail_first') else "false"
    st.html(f'''<script>if(window.ieumLatest!=={seq}){{window.ieumLatest={seq};
    window.ieumDetailScroll?.();
    const interaction=window.ieumInteractionSeq||0;
    let observer;
    const stop=()=>observer?.disconnect();
    const show=()=>{{if((window.ieumInteractionSeq||0)!==interaction){{stop();return;}}
    if(document.querySelector('[data-testid=stPopoverButton][aria-expanded=true]'))return;
    document.getElementById('latest-reply-{seq}')?.scrollIntoView({{block:'start'}});}};
    setTimeout(show,150);setTimeout(show,600);
    if({detail_scroll}){{
      const reply=document.getElementById('latest-reply-{seq}')?.closest('[data-testid=stChatMessage]');
      if(reply){{observer=new ResizeObserver(()=>requestAnimationFrame(show));observer.observe(reply);}}
      window.ieumDetailScroll=stop;
      setTimeout(show,1200);setTimeout(show,2000);setTimeout(stop,2500);
    }}
    }}</script>''',unsafe_allow_javascript=True)

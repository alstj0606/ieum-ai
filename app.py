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
from services.dialogue import new_state, handle_turn, manual_search, application_guide, basic_extract
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
                   "turn_seq":0, "speech_error":None, "voice_error":None, "transcript":None, "upload_seen":None, "edit_voice":False}.items():
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
    spoken = speech_text(state["message"], rows)
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
        if reference:
            st.warning("참고 자료예요. 지금 신청 가능하다고 확인된 활동은 아니에요.")
        for label, value in (("장소",row["facility_name"] or "확인 필요"),
                             ("시간",facts["일정"]),("비용",facts["비용"]),("접수 상태",facts["접수 상태"])):
            display_value = value.replace("~", "\\~")  # Preserve official date/time ranges in Markdown.
            st.write(f"**{label}** · {display_value}")
        with st.expander("자세히 보기"):
            for label in ("주소","대상","신청 방법","정보 확인일","접수 참고","비용 참고"):
                if label in facts:
                    st.write(f"**{label}** · {facts[label]}")
            st.write("**준비물** · 확인 필요")
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
        if not settings.api_key:
            st.caption("지금은 기본 글 검색을 이용할 수 있어요. AI·음성은 연결 설정 후 사용할 수 있어요.")

with st.popover("＋ 보조 메뉴", use_container_width=False):
    with st.expander("AI 도움 없이 찾아보기"):
        with st.form("manual_form"):
            category=st.selectbox("활동 분류",["전체","체육","문화·취미","평생학습"],key="manual_category")
            slot=st.selectbox("편한 시간",["상관없음","오전","오후","저녁"],key="manual_time")
            if st.form_submit_button("선택한 조건으로 찾기",key="manual_submit"):
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
                submit_voice(uploaded)
    with st.expander("예시 체험 · 가상 수영 프로그램"):
        if st.button("초보 수영 찾기",key="demo_example"):
            demo=json.loads((ROOT/"data/demo_program.json").read_text())
            state=new_state()
            state.update(message="시연용 데이터 · 가상 프로그램 · 실제 신청 불가",code="demo",demo=demo)
            remember("초보 수영 예시 체험",state,preserve=True)
            st.rerun()
    with st.expander("자료와 이용 안내"):
        st.write(f"서울 강서구 공식 자료 {len(activities)}건이며 실시간 접수 정보는 아니에요.")
        st.write("녹음 종료 후 OpenAI로 음성을 보내 글로 바꾸고 검색해요. 조용해져도 자동 종료하지 않아요. 1분 이내로 말씀해 주세요.")
        st.write("AI는 조건만 이해해요. 실제 신청·예약·결제는 하지 않아요.")
        st.write("마이크 권한을 허용하고 HTTPS 주소를 직접 열어주세요. 마이크가 안 되면 글로 계속 질문할 수 있어요.")
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
            if state.get("notice"):
                st.info(state["notice"])
            if state.get("diagnostic"):
                with st.expander("연결 상태 확인"):
                    code = state["diagnostic"]["code"]
                    st.write(f"진단 코드: {code}")
                    st.write(DIAGNOSTICS.get(code, DIAGNOSTICS["unknown"]))
            st.write(state["message"])
            if state["code"]=="demo":
                demo=state["demo"]
                st.subheader(demo["name"])
                for label,key in (("대상","audience"),("시간","schedule"),("비용","fee"),("접수 기간","registration_period")):
                    st.write(f"**{label}** · {demo[key]}")
            else:
                rows=state["results"] or state["references"]
                for position,row in enumerate(rows[:3]):
                    card(row,index,position,reference=not bool(state["results"]),latest=latest)
            if latest and state["code"] not in {"demo","start"}:
                if state["pending"]=="region":
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
if st.session_state.turns:
    seq=st.session_state.turn_seq
    st.html(f'''<script>if(window.ieumLatest!=={seq}){{window.ieumLatest={seq};
    document.querySelector('[data-testid=stPopoverButton][aria-expanded=true]')?.click();
    const show=()=>document.getElementById('latest-reply-{seq}')?.scrollIntoView({{block:'start'}});
    setTimeout(show,150);setTimeout(show,600);}}</script>''',unsafe_allow_javascript=True)

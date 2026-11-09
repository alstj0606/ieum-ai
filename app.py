"""공식 활동 데이터와 대화·음성 입력을 연결하는 이음 AI."""

import json
from pathlib import Path

import streamlit as st

from services.activities import load_activities
from services.config import load_settings
from services.dialogue import new_state, handle_turn, manual_search, application_guide, basic_extract
from services.recommendations import activity_facts, speech_text, known
from services.voice import transcribe, synthesize, VoiceError


st.set_page_config(page_title="이음 AI · 활동 찾기", page_icon="🌊")
st.markdown(
    """
    <style>
    .stMainBlockContainer {
        max-width: 760px; padding: 5rem 1rem 4rem;
    }
    .stMain h1 { font-size: 2.5rem !important; line-height: 1.3; }
    .stMain h2 { font-size: 1.75rem !important; line-height: 1.5; }
    .stMain h3 { font-size: 1.5rem !important; line-height: 1.5; }
    .stMain .stMarkdown p, .stTextArea label p, .stSelectbox label p,
    .stMain .stAlert p, .stMain .stExpander summary p,
    .stButton button p, .stFormSubmitButton button p {
        font-size: 1.25rem !important; line-height: 1.75;
    }
    .stTextArea textarea {
        font-size: 1.25rem !important; line-height: 1.75;
        padding: 0.85rem;
    }
    .stSelectbox [data-baseweb="select"] { font-size: 1.25rem; }
    .stMain .stText pre {
        font-size: 1.25rem; line-height: 1.75; font-family: inherit;
        white-space: pre-wrap; overflow-wrap: anywhere;
    }
    .stMain .stExpander summary { min-height: 56px; }
    .stLinkButton a p { font-size: 1.25rem !important; }
    .stTextArea textarea::placeholder { opacity: 1; }
    .stButton button, .stFormSubmitButton button, .stLinkButton a,
    [data-testid="stAudioInput"] button {
        min-height: 64px; height: auto; padding: 0.85rem 1rem;
        border-radius: 12px;
    }
    .stButton button:focus-visible, .stFormSubmitButton button:focus-visible,
    .stTextArea textarea:focus-visible {
        outline: 3px solid #1671c5; outline-offset: 3px;
    }
    .stMain .stMarkdown p, .stMain h1, .stMain h2, .stMain h3, button p {
        overflow-wrap: anywhere; word-break: normal; white-space: normal;
    }
    .stMain [data-testid="stVerticalBlock"] { gap: 1.25rem; }
    .stMain [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 16px;
    }
    @media (max-width: 480px) {
        .stMainBlockContainer { padding: 5rem 1rem 3rem; }
        .stMain h1 { font-size: 2.25rem !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

program = json.loads(
    (Path(__file__).parent / "data" / "demo_program.json").read_text(encoding="utf-8")
)
try:
    secret_values = dict(st.secrets)
except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
    secret_values = {}
except Exception:
    # 설정 파싱 오류 원문에 비밀 값이 포함될 수 있어 그대로 출력하지 않는다.
    secret_values = {}
    st.warning("서버 연결 설정을 읽지 못했어요. 기본 검색은 계속 이용할 수 있어요.")
settings = load_settings(secret_values)
del secret_values
try:
    activities = load_activities()
except (OSError, ValueError):
    st.error("공식 자료를 읽지 못했어요. 잠시 후 다시 시도해 주세요. 예시 체험은 계속 이용할 수 있어요.")
    activities = []

for key, default in {
    "dialog": new_state(), "question": "", "demo_visible": False,
    "speech_bytes": None, "speech_source": None, "voice_error": None,
    "voice_notice": None, "clear_input": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default
if st.session_state.clear_input:
    st.session_state.question = ""
    st.session_state.clear_input = False


def clear_speech():
    st.session_state.speech_bytes = None
    st.session_state.speech_source = None


def reset_dialog():
    st.session_state.dialog = new_state()
    st.session_state.question = ""
    st.session_state.demo_visible = False
    st.session_state.voice_error = None
    st.session_state.voice_notice = None
    clear_speech()


def quick_turn(text):
    # 화면의 고정 선택 버튼은 LLM 없이 처리해 연결 오류 때도 동작하게 한다.
    state = st.session_state.dialog
    st.session_state.dialog = handle_turn(
        state, text, activities, settings, extraction=basic_extract(text, state)
    )
    st.session_state.question = ""
    clear_speech()


def choose_activity(activity_id):
    st.session_state.dialog = application_guide(
        st.session_state.dialog, activities, selected_id=activity_id
    )
    clear_speech()


def show_example():
    # 실제 검색 상태를 가상 결과로 바꾸지 않는 독립 체험이다.
    st.session_state.demo_visible = True
    st.session_state.question = "수영을 처음 배우는데 할 수 있어?"


st.title("이음 AI")
st.header("오늘은 어떤 활동을 찾으세요?")
st.write("운동, 만들기, 공연, 배움까지 함께 찾아봐요.")
st.info(f"서울 강서구 공식 자료 {len(activities)}건 · 실시간 접수 정보가 아니에요.")
if not settings.api_key:
    st.info("기본 검색 모드 · 글이나 조건 선택으로 찾아요. AI·음성은 연결 설정 후 이용할 수 있어요.")
else:
    st.write("질문을 보내면 AI가 조건을 정리해요. 활동 정보는 공식 자료에서만 보여드려요.")

with st.expander("🎤 말로 입력하기"):
    st.write("녹음 시작을 누르고 말씀한 뒤 녹음을 끝내세요. 1분 이내로 말씀해 주세요.")
    st.write("‘음성을 글로 바꾸기’를 누르면 녹음을 OpenAI에 보내 변환해요. 변환된 글을 확인·수정한 뒤 질문을 보내세요.")
    recording = st.audio_input("마이크로 질문 녹음", key="voice_recording", disabled=not bool(settings.api_key))
    uploaded = st.file_uploader(
        "녹음이 안 되면 음성 파일 선택 (선택 사항)", type=["wav", "m4a", "mp3", "webm"],
        key="voice_upload", disabled=not bool(settings.api_key),
    )
    if st.button("음성을 글로 바꾸기", key="transcribe", use_container_width=True,
                 disabled=not bool(settings.api_key) or (recording is None and uploaded is None)):
        st.session_state.voice_error = None
        audio = recording if recording is not None else uploaded
        if audio is None:
            st.session_state.voice_error = "녹음을 먼저 해주세요. 마이크가 안 되면 아래에 글로 적어도 돼요."
        else:
            try:
                with st.spinner("말씀을 글로 바꾸고 있어요…"):
                    st.session_state.question = transcribe(
                        audio.getvalue(), settings, filename=audio.name
                    )
                st.session_state.voice_notice = "아래 입력창의 글이 맞는지 확인하고 고쳐주세요. 아직 질문을 보내지는 않았어요."
            except VoiceError as error:
                st.session_state.voice_error = str(error)
    st.write("녹음이 안 되나요? Safari·브라우저 설정에서 마이크 권한을 허용하고 HTTPS의 앱 주소를 직접 열어주세요. 지원하지 않는 기기에서는 글 입력이나 파일 선택을 이용해 주세요.")
if st.session_state.voice_error:
    st.warning(st.session_state.voice_error)
if st.session_state.voice_notice:
    st.info(st.session_state.voice_notice)

st.subheader("궁금한 내용을 적어주세요")
with st.container(border=False):
    st.text_area(
        "어떤 활동을 하고 싶으세요?", placeholder="예: 오전에 사람들과 식물을 가꾸고 싶어요",
        key="question", height=150, max_chars=1500,
    )
    submitted = st.button(
        "프로그램 찾아보기", type="primary", use_container_width=True, key="submit_question"
    )
if submitted:
    with st.spinner("말씀하신 조건을 확인하고 있어요…"):
        st.session_state.dialog = handle_turn(
            st.session_state.dialog, st.session_state.question, activities, settings
        )
    clear_speech()
    st.session_state.clear_input = not bool(st.session_state.dialog["error"])
    st.session_state.voice_notice = None
    st.rerun()

state = st.session_state.dialog
if state["error"]:
    st.warning(state["error"])
if len(state["history"]) > 2:
    with st.expander("이전 대화 보기"):
        for turn in state["history"][:-2]:
            with st.chat_message(turn["role"]):
                st.write(turn["content"])
if state["history"]:
    for turn in state["history"][-2:]:
        with st.chat_message(turn["role"]):
            st.write(turn["content"])
else:
    st.write(state["message"])

if state["conditions"]:
    labels = {"region": "찾는 지역", "category": "활동 분류", "activity_type": "활동 종류",
              "time_slot": "시간대", "budget_amount": "예산(원)", "budget_unit": "예산 단위",
              "purpose": "참여 목적", "beginner": "초보 여부", "age": "말씀하신 나이",
              "gender": "말씀하신 성별", "residence": "거주지", "tags": "관심"}
    with st.expander("지금까지 말씀하신 조건"):
        for key, value in state["conditions"].items():
            if type(value) is bool:
                value = "예" if value else "아니요"
            st.write(f"{labels[key]}: {value}")
if state["pending"] == "region":
    st.button("서울 강서구에서 찾기", key="choose_region", on_click=quick_turn,
              args=("서울 강서구요",), use_container_width=True)
elif state["pending"] == "time_slot":
    for name in ("오전", "오후", "저녁", "상관없어요"):
        st.button(name, key=f"time_{name}", on_click=quick_turn, args=(name,), use_container_width=True)
elif state["pending"] == "budget_unit":
    for name in ("한 번 금액이에요", "한 달 금액이에요"):
        st.button(name, key=f"budget_{name}", on_click=quick_turn, args=(name,), use_container_width=True)

with st.expander("조건을 골라 직접 찾기 · AI 없이도 가능"):
    st.write("서울 강서구 공식 자료에서 찾아요. 이 버튼은 이전 대화 조건을 새 선택으로 바꿔요.")
    with st.form("manual_form"):
        category = st.selectbox("활동 분류", ["전체", "체육", "문화·취미", "평생학습"], key="manual_category")
        slot = st.selectbox("편한 시간", ["상관없음", "오전", "오후", "저녁"], key="manual_time")
        direct = st.form_submit_button("선택한 조건으로 찾기", use_container_width=True, key="manual_submit")
    if direct:
        st.session_state.dialog = manual_search(
            state, activities, category=None if category == "전체" else category,
            time_slot=None if slot == "상관없음" else slot,
        )
        clear_speech()
        st.session_state.clear_input = True
        st.rerun()


def render_activity(item, index, *, reference=False):
    with st.container(border=True):
        st.subheader(f"{index}. {item['name']}")
        if item["id"] == state["selected_id"]:
            st.info("신청 방법을 선택한 활동이에요. 실제 신청은 공식 페이지에서 진행해 주세요.")
        if reference:
            st.warning("참고 자료예요. 지금 조건으로 신청 가능하다고 확인한 결과가 아니에요.")
        for label, value in activity_facts(item):
            st.markdown(f"**{label}**")
            st.write(value)
        for note in item.get("condition_notes", []):
            st.warning(note)
        with st.expander("자료의 미확인 사항·주의사항"):
            st.write(known(item["schedule"].get("notes")))
            for note in item.get("verification_notes", []):
                st.write(note)
        st.link_button("공식 출처 확인", item["source_url"], use_container_width=True)
        if item["official_url"]:
            st.link_button("공식 안내·신청 페이지 열기", item["official_url"], use_container_width=True)
        else:
            st.write("공식 신청 링크는 확인이 필요해요.")
        if not reference:
            st.button("이 활동 신청 방법", key=f"apply_{item['id']}", on_click=choose_activity,
                      args=(item["id"],), use_container_width=True)


if state["code"] != "start":
    st.subheader("안내 듣기")
    spoken_results = state["results"] or state["references"]
    if state["selected_id"]:
        spoken_results = [item for item in spoken_results if item["id"] == state["selected_id"]]
    spoken = speech_text(state["message"], spoken_results)
    with st.expander("음성으로 읽는 내용 · 화면에서도 확인"):
        st.text(spoken)
    st.write("AI가 만든 음성으로 읽어드려요. 준비 후 재생(▶)을 눌러주세요. 자동 재생하지 않아요.")
    if st.button("답변 듣기", key="prepare_speech", use_container_width=True, disabled=not bool(settings.api_key)):
        try:
            with st.spinner("읽어드릴 음성을 준비하고 있어요…"):
                st.session_state.speech_bytes = synthesize(spoken, settings)
                st.session_state.speech_source = spoken
        except VoiceError as error:
            clear_speech()
            st.warning(str(error))
    if st.session_state.speech_bytes and st.session_state.speech_source == spoken:
        if st.button("음성 중지", key="stop_speech", use_container_width=True):
            clear_speech()
            st.rerun()
        st.audio(st.session_state.speech_bytes, format="audio/mp3", autoplay=False)
        st.write("재생·일시정지는 위 재생기에서 할 수 있어요. 소리가 안 나면 화면의 글을 확인해 주세요.")

if state["results"]:
    st.divider()
    st.header("찾아본 공식 활동")
    st.write("최대 3개를 보여드려요. 접수중 표시는 예약 성공이나 당일 참여를 보장하지 않아요.")
    for index, item in enumerate(state["results"], 1):
        render_activity(item, index)
elif state["references"]:
    st.header("확인이 필요한 관련 자료")
    for index, item in enumerate(state["references"], 1):
        render_activity(item, index, reference=True)

if state["code"] != "start":
    st.button("다른 시간으로 찾기", key="change_time", on_click=quick_turn,
              args=("다른 시간",), use_container_width=True)
    st.button("다른 활동 찾기", key="change_activity", on_click=quick_turn,
              args=("다른 활동",), use_container_width=True)
    st.button("같은 조건으로 다시 검색", key="retry_search", on_click=quick_turn,
              args=("같은 조건으로 다시 찾아주세요",), use_container_width=True)
st.button("처음부터 다시 찾기", key="reset", on_click=reset_dialog, use_container_width=True)

st.divider()
st.subheader("예시 체험 · 가상 수영 프로그램")
st.write("공식 추천과 별개인 화면 체험이에요. AI·API 키 없이도 볼 수 있어요.")
st.button("초보 수영 찾기", key="demo_example", on_click=show_example, use_container_width=True)
if st.session_state.demo_visible:
    with st.container(border=True):
        st.warning("시연용 데이터 · 가상 프로그램 · 실제 신청 불가")
        st.subheader(program["name"])
        for label, key in [("대상", "audience"), ("시간", "schedule"), ("비용", "fee"), ("접수 기간", "registration_period")]:
            st.markdown(f"**{label}**")
            st.write(program[key])
        st.write("시설은 미정이에요. 공식 추천 결과나 실제 프로그램이 아니에요.")

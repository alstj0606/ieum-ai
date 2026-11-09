"""이음 AI의 API 키 없는 첫 화면 시연."""

import json
from pathlib import Path

import streamlit as st


st.set_page_config(page_title="이음 AI · 수영 프로그램 찾기", page_icon="🌊")
st.markdown(
    """
    <style>
    .stMainBlockContainer {
        max-width: 760px; padding: 5rem 1rem 4rem;
    }
    .stMain h1 { font-size: 2.5rem !important; line-height: 1.3; }
    .stMain h2 { font-size: 1.75rem !important; line-height: 1.5; }
    .stMain h3 { font-size: 1.5rem !important; line-height: 1.5; }
    .stMain .stMarkdown p, .stTextArea label p,
    .stButton button p, .stFormSubmitButton button p {
        font-size: 1.25rem !important; line-height: 1.75;
    }
    .stTextArea textarea {
        font-size: 1.25rem !important; line-height: 1.75;
        padding: 0.85rem;
    }
    .stTextArea textarea::placeholder { opacity: 1; }
    .stButton button, .stFormSubmitButton button {
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


def show_example():
    st.session_state.question = "수영을 처음 배우는데 할 수 있어?"
    st.session_state.show_result = True
    st.session_state.feedback = "success"


st.title("이음 AI")
st.header("오늘은 어떤 활동을 찾으세요?")
st.write("지금은 수영 프로그램 예시를 볼 수 있어요.")
st.info("시연용 가상 데이터입니다. 실제 프로그램 검색이나 신청은 할 수 없어요.")

st.subheader("궁금한 내용을 적어주세요")
with st.form("question_form", border=False):
    st.text_area(
        "수영에 대해 무엇이 궁금하세요?",
        placeholder="예: 수영을 처음 배우는데 할 수 있어?",
        key="question",
        height=150,
    )
    # 폼은 질문과 제출을 함께 보내므로 입력 직후 눌러도 같은 값을 처리합니다.
    input_feedback = st.empty()
    submitted = st.form_submit_button(
        "프로그램 찾아보기", type="primary", use_container_width=True
    )

if submitted:
    if st.session_state.question.strip():
        st.session_state.show_result = True
        st.session_state.feedback = "success"
    else:
        st.session_state.show_result = False
        st.session_state.feedback = "empty"

if st.session_state.get("feedback") == "empty":
    input_feedback.warning("질문을 먼저 적어주세요")
elif st.session_state.get("feedback") == "success":
    st.success("시연 결과를 아래에 표시했어요")

st.write("무엇을 적을지 고민되면 아래 버튼을 눌러보세요.")
st.button("초보 수영 찾기", on_click=show_example, use_container_width=True)

if st.session_state.get("show_result", False):
    st.divider()
    st.header("찾아본 프로그램 · 시연 예시")
    st.write("아직 질문을 분석하지 않아요. 어떤 질문을 적어도 같은 시연용 예시를 보여드립니다.")
    with st.container(border=True):
        st.markdown("**시연용 데이터 · 가상 프로그램**")
        st.subheader(program["name"])
        for label, key in [("대상", "audience"), ("시간", "schedule"), ("비용", "fee"), ("접수 기간", "registration_period")]:
            st.markdown(f"**{label}**  \n{program[key]}")
        st.info("시설은 아직 정해지지 않았어요. 이 프로그램은 가상 예시이며 신청할 수 없어요.")

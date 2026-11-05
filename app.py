"""이음 AI의 API 키 없는 첫 화면 시연."""

import json
from pathlib import Path

import streamlit as st


st.set_page_config(page_title="이음 AI · 수영 프로그램 찾기", page_icon="🌊")
st.markdown(
    """
    <style>
    .stMainBlockContainer { max-width: 800px; }
    h1 { font-size: 3rem !important; }
    .stMarkdown p, .stTextArea label p, .stButton button p,
    .stFormSubmitButton button p {
        font-size: 1.25rem !important; line-height: 1.7;
    }
    .stTextArea textarea { font-size: 1.2rem; line-height: 1.6; }
    .stButton button, .stFormSubmitButton button {
        min-height: 56px; height: auto; padding: 0.65rem 1rem;
    }
    .stMarkdown p, h1, h2, h3, button p {
        overflow-wrap: anywhere; word-break: normal; white-space: normal;
    }
    @media (max-width: 480px) {
        .stMainBlockContainer { padding: 2rem 1rem; }
        h1 { font-size: 2.4rem !important; }
        h2, h3 { font-size: 1.5rem !important; }
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
st.markdown("### 배우고 싶은 수영, 함께 찾아봐요")
st.write("궁금한 내용을 적거나 ‘초보 수영 찾기’를 눌러보세요.")
st.info("시연용 데이터 · 시설은 미정이며, 실제로 신청할 수 있는 프로그램이 아닙니다.")

with st.form("question_form", border=False):
    st.text_area(
        "수영에 대해 무엇이 궁금하세요?",
        placeholder="예: 수영을 처음 배우는데 할 수 있어?",
        key="question",
        height=110,
    )
    # 폼은 질문과 제출을 함께 보내므로 입력 직후 눌러도 같은 값을 처리합니다.
    input_feedback = st.empty()
    submitted = st.form_submit_button("입력한 질문으로 시연 보기", use_container_width=True)

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

st.button("초보 수영 찾기", on_click=show_example, type="primary", use_container_width=True)

if st.session_state.get("show_result", False):
    st.subheader("수영 프로그램 예시")
    st.write("아직 질문을 분석하지 않아요. 어떤 질문을 적어도 같은 시연용 예시를 보여드립니다.")
    with st.container(border=True):
        st.markdown("**시연용 데이터 · 가상 프로그램**")
        st.subheader(program["name"])
        for label, key in [("대상", "audience"), ("시간", "schedule"), ("비용", "fee"), ("접수 기간", "registration_period")]:
            st.markdown(f"**{label}**  \n{program[key]}")
        st.write("시설: 미정 · 공식 신청 연결은 실제 시설을 선정한 뒤 제공할 예정입니다.")

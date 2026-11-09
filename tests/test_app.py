"""Streamlit 세션/UI 회귀 검사. 유료 API는 모두 모의 처리한다."""

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
import json

from streamlit.testing.v1 import AppTest

from services.activities import load_activities
from services.ai import empty_extraction
from services.config import Settings
from services.dialogue import manual_search, new_state
from services.voice import VoiceError


APP = str(Path(__file__).resolve().parents[1] / "app.py")
DAY = date(2026, 11, 9)


class AppFlowTest(TestCase):
    def test_manual_search_and_official_values_with_no_key(self):
        with patch("services.config.load_settings", return_value=Settings()):
            app = AppTest.from_file(APP).run()
            app.selectbox(key="manual_category").select("문화·취미")
            app.selectbox(key="manual_time").select("오전")
            app.button(key="manual_submit").click().run()
            self.assertFalse(app.exception)
            state = app.session_state["dialog"]
            self.assertLessEqual(len(state["results"]), 3)
            self.assertTrue(state["results"])
            for row in state["results"]:
                self.assertTrue(any(row["name"] in item.value for item in app.subheader))
                self.assertTrue(any(row["schedule"]["text"] in item.value for item in app.markdown))
            before = state["results"]
            app.button(key="demo_example").click().run()
            self.assertEqual(app.session_state["dialog"]["results"], before)
            self.assertTrue(any("가상 프로그램" in item.value for item in app.subheader))

    def test_ai_submit_calls_once_and_failure_keeps_text(self):
        payload = empty_extraction()
        payload["conditions"].update(region="서울 강서구", activity_type="가드닝")
        payload["update_fields"] = ["region", "activity_type"]
        client = Mock()
        client.responses.create.return_value = SimpleNamespace(
            status="completed", output_text=json.dumps(payload, ensure_ascii=False)
        )
        with patch("services.config.load_settings", return_value=Settings(api_key="mock-test-only")), \
                patch("services.ai.make_client", return_value=client):
            app = AppTest.from_file(APP).run()
            app.text_area(key="question").input("강서구에서 식물 키우기")
            app.button(key="submit_question").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["dialog"]["code"], "found")
            self.assertEqual(client.responses.create.call_count, 1)
            app.run()
            self.assertEqual(client.responses.create.call_count, 1)
            client.responses.create.side_effect = TimeoutError("sensitive response")
            app.text_area(key="question").input("다른 시간에요")
            app.button(key="submit_question").click().run()
            self.assertEqual(app.text_area(key="question").value, "다른 시간에요")
            self.assertTrue(any("AI 연결" in item.value for item in app.warning))
            self.assertFalse(any("sensitive response" in item.value for item in app.warning))

    def test_stt_failure_preserves_editable_text(self):
        recording = SimpleNamespace(name="question.wav", getvalue=lambda: b"test")
        with patch("services.config.load_settings", return_value=Settings(api_key="mock-test-only")), \
                patch("streamlit.audio_input", return_value=recording), \
                patch("services.voice.transcribe", side_effect=VoiceError("음성 인식 실패. 글로 적어주세요.")):
            app = AppTest.from_file(APP).run()
            app.text_area(key="question").input("이전 질문")
            app.button(key="transcribe").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.text_area(key="question").value, "이전 질문")
            self.assertTrue(any("음성 인식 실패" in item.value for item in app.warning))

    def test_tts_failure_preserves_text_and_stop_clears_media(self):
        with patch("services.config.load_settings", return_value=Settings(api_key="mock-test-only")), \
                patch("services.voice.synthesize", side_effect=VoiceError("음성 안내 실패")) as synth:
            app = AppTest.from_file(APP).run()
            app.session_state["dialog"] = manual_search(new_state(), load_activities(), as_of=DAY)
            app.run()
            app.button(key="prepare_speech").click().run()
            self.assertFalse(app.exception)
            self.assertTrue(app.session_state["dialog"]["results"])
            self.assertTrue(any("음성 안내 실패" in item.value for item in app.warning))
            synth.side_effect = None
            synth.return_value = b"mock-audio-not-real-speech"
            app.button(key="prepare_speech").click().run()
            self.assertTrue(app.session_state["speech_bytes"])
            app.button(key="stop_speech").click().run()
            self.assertIsNone(app.session_state["speech_bytes"])

    def test_second_selection_reads_selected_activity(self):
        with patch("services.config.load_settings", return_value=Settings(api_key="mock-test-only")), \
                patch("services.voice.synthesize", return_value=b"mock-audio") as synth:
            app = AppTest.from_file(APP).run()
            state = manual_search(new_state(), load_activities(), as_of=DAY)
            selected = state["results"][1]
            app.session_state["dialog"] = state
            app.run()
            app.button(key=f"apply_{selected['id']}").click().run()
            app.button(key="prepare_speech").click().run()
            self.assertFalse(app.exception)
            read_text = synth.call_args.args[0]
            self.assertIn(selected["name"], read_text)
            self.assertNotIn(state["results"][0]["name"], read_text)

"""API 응답은 모의 객체다. 실제 OpenAI 인식 품질을 검증한 테스트가 아니다."""

from copy import deepcopy
from datetime import date
from io import BytesIO
import json
import os
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
import wave

from services.activities import load_activities
from services.ai import AIError, empty_extraction, extract_conditions, make_client, validate_extraction
from services.config import Settings, load_settings
from services.dialogue import new_state, handle_turn, manual_search, application_guide
from services.recommendations import recommend, activity_facts, speech_text
from services.voice import VoiceError, synthesize, transcribe


DAY = date(2026, 11, 9)


def extraction(**conditions):
    result = empty_extraction()
    result["conditions"].update(conditions)
    result["update_fields"] = list(conditions)
    return result


def mock_client(payload):
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(
        status="completed", output_text=json.dumps(payload, ensure_ascii=False)
    )
    return client


def wav_bytes(*, silent=False):
    stream = BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(16000)
        audio.writeframes((b"\0\0" if silent else b"\x10\x01") * 8000)
    return stream.getvalue()


class DialogueTest(TestCase):
    def setUp(self):
        self.rows = load_activities()
        self.settings = Settings()

    def turn(self, state, text, **kwargs):
        return handle_turn(state, text, self.rows, self.settings, as_of=DAY, **kwargs)

    def test_basic_dialect_region_followup_and_no_match(self):
        state = self.turn(new_state(), "수영이 처음인디 어디서 배우면 돼유?")
        self.assertEqual(state["pending"], "region")
        self.assertTrue(state["conditions"]["beginner"])
        state = self.turn(state, "강서구요")
        self.assertEqual(state["conditions"]["activity_type"], "수영")
        self.assertEqual(state["code"], "no_match")
        self.assertIsNone(state["pending"])
        self.assertIn("자료", state["message"])
        self.assertEqual(state["mode"], "basic")

    def test_accumulate_change_and_any(self):
        state = self.turn(new_state(), "강서구 오전 가드닝")
        state = self.turn(state, "오전 말고 오후요")
        self.assertEqual(state["conditions"]["time_slot"], "오후")
        self.assertEqual(state["conditions"]["activity_type"], "가드닝")
        state = self.turn(state, "다른 시간")
        self.assertEqual(state["pending"], "time_slot")
        state = self.turn(state, "상관없어요")
        self.assertNotIn("time_slot", state["conditions"])
        self.assertEqual(state["code"], "found")

    def test_region_any_does_not_repeat_question(self):
        state = self.turn(new_state(), "국악")
        state = self.turn(state, "상관없어요")
        self.assertIsNone(state["pending"])
        self.assertIn("region", state["any_fields"])
        self.assertEqual(state["code"], "found")

    def test_ai_conditions_context_and_request_contract(self):
        payload = extraction(region="강서구", activity_type="가드닝", time_slot="오전", purpose="배우기")
        client = mock_client(payload)
        state = handle_turn(new_state(), "아침에 식물 키우기를 배우고 싶어요", self.rows,
                            Settings(api_key="test-only"), client=client, as_of=DAY)
        self.assertEqual(state["mode"], "openai")
        self.assertEqual(state["code"], "found")
        args = client.responses.create.call_args.kwargs
        self.assertFalse(args["store"])
        self.assertTrue(args["text"]["format"]["strict"])
        self.assertNotIn("official_url", args["input"])
        self.assertNotIn("fee_amount", args["input"])
        # 후속 응답에도 이미 정리한 조건·대화 문맥을 전달한다.
        client.responses.create.return_value.output_text = json.dumps(extraction(time_slot="오후"))
        followup = handle_turn(state, "오후로 바꿔주세요", self.rows,
                               Settings(api_key="test-only"), client=client, as_of=DAY)
        context = json.loads(client.responses.create.call_args.kwargs["input"])
        self.assertEqual(context["current_conditions"]["time_slot"], "오전")
        self.assertTrue(context["history"])
        self.assertEqual(followup["conditions"]["time_slot"], "오후")

    def test_reject_generated_facts_and_malformed_values(self):
        bad = extraction(region="강서구")
        bad["program_name"] = "가짜 강좌"
        bad_values = [bad, extraction(region="https://invented.invalid"),
                      extraction(age=True), extraction(budget_amount=-1),
                      extraction(beginner="예"), extraction(tags="국악")]
        for payload in bad_values:
            with self.subTest(payload=payload), self.assertRaises(AIError):
                validate_extraction(payload)

    def test_clear_and_update_same_field_rejected(self):
        payload = extraction(time_slot="오후")
        payload["clear_fields"] = ["time_slot"]
        with self.assertRaises(AIError):
            validate_extraction(payload)

    def test_api_timeout_and_error_do_not_destroy_previous_state(self):
        state = self.turn(new_state(), "강서구 국악")
        before = deepcopy(state)
        for error in (TimeoutError("secret-not-to-show"), RuntimeError("secret-not-to-show")):
            client = Mock(); client.responses.create.side_effect = error
            changed = handle_turn(state, "오후요", self.rows, Settings(api_key="test-only"),
                                  client=client, as_of=DAY)
            self.assertEqual(changed["conditions"], before["conditions"])
            self.assertEqual(changed["results"], before["results"])
            self.assertNotIn("secret-not-to-show", changed["error"])

    def test_incomplete_refused_and_invalid_json(self):
        client = mock_client({})
        for status, output in (("incomplete", ""), ("completed", ""), ("completed", "not json")):
            client.responses.create.return_value = SimpleNamespace(status=status, output_text=output)
            with self.assertRaises(AIError):
                extract_conditions("질문", new_state(), self.rows, Settings(api_key="test-only"), client=client)

    def test_keys_missing_and_config_secrets_priority(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "OPENAI_MODEL": ""}):
            self.assertFalse(load_settings().api_key)
            self.assertEqual(load_settings({"OPENAI_API_KEY": "server-secret"}).api_key, "server-secret")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-secret"}):
            self.assertEqual(load_settings({"OPENAI_API_KEY": "other"}).api_key, "env-secret")
        self.assertNotIn("env-secret", repr(Settings(api_key="env-secret")))
        with self.assertRaises(AIError):
            make_client(Settings())

    def test_closed_unknown_qualification_and_insufficient_are_distinct(self):
        cases = [
            ({"activity_type": "슬로우조깅"}, "closed"),
            ({"activity_type": "아쿠아로빅"}, "unknown"),
            ({"activity_type": "숲체험", "gender": "남성"}, "qualification"),
            ({"activity_type": "슬로우조깅", "age": 30}, "qualification"),
            ({"activity_type": "가드닝", "budget_amount": 10000, "budget_unit": "월"}, "insufficient"),
            ({"activity_type": "수영"}, "no_match"),
        ]
        for conditions, expected in cases:
            with self.subTest(expected=expected):
                result = recommend(self.rows, conditions, as_of=DAY)
                self.assertEqual(result["code"], expected)
                self.assertEqual(result["results"], [])

    def test_beginner_training_requirement_and_unknown_eligibility(self):
        result = recommend(self.rows, {"activity_type": "파크골프", "beginner": True}, as_of=DAY)
        self.assertEqual(result["code"], "qualification")
        result = recommend(self.rows, {"activity_type": "숲체험"}, as_of=DAY)
        self.assertTrue(any("여성" in note for note in result["results"][0]["condition_notes"]))

    def test_budget_unit_not_guessed_and_free_preserved(self):
        state = self.turn(new_state(), "강서구 만 원")
        # 숫자 표현은 기본 모드에서 제한적이다. 구조화된 AI 응답으로 금액 누적을 검증한다.
        state = self.turn(state, "만원 예산", extraction=extraction(budget_amount=10000))
        self.assertEqual(state["pending"], "budget_unit")
        state = self.turn(state, "한 달 금액이에요")
        self.assertEqual(state["conditions"]["budget_unit"], "월")
        result = recommend(self.rows, {"budget_amount": 0}, as_of=DAY)
        self.assertTrue(result["results"])
        self.assertTrue(all(row["fee_amount"] == 0 for row in result["results"]))

    def test_application_yes_no_and_selection_never_book(self):
        state = self.turn(new_state(), "강서구 국악 관람")
        state = self.turn(state, "신청하고 싶어요")
        self.assertEqual(state["code"], "apply")
        self.assertIn("완료된 것은 아니", state["message"])
        state = self.turn(state, "네")
        self.assertIn("직접", state["message"])
        state = self.turn(state, "아니요")
        self.assertEqual(state["code"], "clarify")
        multiple = manual_search(new_state(), self.rows, as_of=DAY)
        multiple = self.turn(multiple, "신청하고 싶어요")
        self.assertEqual(multiple["pending"], "selection")
        selected = self.turn(multiple, "두 번째 신청")
        self.assertEqual(selected["selected_id"], multiple["results"][1]["id"])
        invalid = application_guide(multiple, self.rows, selected_id="invented-id", as_of=DAY)
        self.assertEqual(invalid["code"], "choose")

    def test_application_rechecks_expired_results(self):
        state = self.turn(new_state(), "강서구 국악")
        state = application_guide(state, self.rows, as_of=date(2026, 11, 15))
        self.assertEqual(state["code"], "closed")
        self.assertEqual(state["results"], [])

    def test_change_activity_clears_incompatible_interest(self):
        state = self.turn(new_state(), "강서구 수영 초보")
        state = self.turn(state, "다른 활동")
        self.assertNotIn("beginner", state["conditions"])
        self.assertNotIn("activity_type", state["conditions"])
        state = self.turn(state, "국악")
        self.assertEqual(state["code"], "found")

    def test_exact_facts_and_speech_come_from_same_data(self):
        for row in self.rows:
            with self.subTest(id=row["id"]):
                facts = activity_facts(row, as_of=DAY)
                text = speech_text("안내", [row], as_of=DAY)
                for label, value in facts:
                    self.assertIn(str(value), text)
                self.assertIn(row["name"], text)
        missing = next(row for row in self.rows if row["fee_amount"] is None)
        self.assertEqual(dict(activity_facts(missing, as_of=DAY))["비용"], "확인 필요")


class VoiceTest(TestCase):
    def test_stt_mock_success_and_korean_language(self):
        client = Mock()
        client.audio.transcriptions.create.return_value = SimpleNamespace(text="수영이 처음인디 어디서 배우면 돼유?")
        result = transcribe(wav_bytes(), Settings(), client=client)
        self.assertIn("처음인디", result)
        self.assertEqual(client.audio.transcriptions.create.call_args.kwargs["language"], "ko")

    def test_stt_invalid_empty_silent_and_oversize(self):
        for data in (b"", b"bad wav", wav_bytes(silent=True), b"0" * (6 * 1024 * 1024)):
            with self.subTest(length=len(data)), self.assertRaises(VoiceError):
                transcribe(data, Settings(), client=Mock())

    def test_stt_api_error_and_empty_result_are_safe(self):
        client = Mock()
        client.audio.transcriptions.create.side_effect = TimeoutError("secret")
        with self.assertRaises(VoiceError) as error:
            transcribe(wav_bytes(), Settings(), client=client)
        self.assertNotIn("secret", str(error.exception))
        client.audio.transcriptions.create.side_effect = None
        client.audio.transcriptions.create.return_value = SimpleNamespace(text="")
        with self.assertRaises(VoiceError):
            transcribe(wav_bytes(), Settings(), client=client)

    def test_tts_sends_exact_visible_text_no_rewrite(self):
        client = Mock()
        client.audio.speech.create.return_value.read.return_value = b"mock-audio"
        text = "접수 마감. 비용은 확인 필요."
        self.assertEqual(synthesize(text, Settings(), client=client), b"mock-audio")
        self.assertEqual(client.audio.speech.create.call_args.kwargs["input"], text)

    def test_tts_slow_speed_and_invalid_speed(self):
        client = Mock()
        client.audio.speech.create.return_value.read.return_value = b"mock-audio"
        synthesize("접수 마감. 비용은 확인 필요.", Settings(), client=client, speed=0.7)
        self.assertEqual(client.audio.speech.create.call_args.kwargs["speed"], 0.7)
        self.assertEqual(client.audio.speech.create.call_args.kwargs["input"], "접수 마감. 비용은 확인 필요.")
        with self.assertRaises(VoiceError):
            synthesize("안내", Settings(), client=client, speed=5)

    def test_tts_error_empty_text_and_missing_key(self):
        client = Mock(); client.audio.speech.create.side_effect = RuntimeError("secret")
        with self.assertRaises(VoiceError) as error:
            synthesize("안내", Settings(), client=client)
        self.assertNotIn("secret", str(error.exception))
        for text in ("", "x" * 4001):
            with self.assertRaises(VoiceError):
                synthesize(text, Settings(), client=client)
        with self.assertRaises(VoiceError):
            synthesize("안내", Settings())
        with self.assertRaises(VoiceError):
            transcribe(wav_bytes(), Settings())

"""명시적인 버튼 조작 때만 음성을 변환한다. 파일·원문을 디스크에 저장하지 않는다."""

from io import BytesIO
import wave

import logging

from services.ai import AIError


def make_voice_client(settings):
    if not settings.api_key:
        raise AIError("OpenAI 음성 API 키가 없어요.", code="key_missing")
    try:
        from openai import OpenAI
        # SDK debug logging may include request bodies. Diagnostics are fixed codes instead.
        for name in ("openai", "openai._base_client", "httpx", "httpcore", "httpx2", "httpcore2"):
            logging.getLogger(name).setLevel(logging.CRITICAL)
        return OpenAI(api_key=settings.api_key, timeout=30.0, max_retries=0)
    except Exception:
        raise AIError("OpenAI 음성 연결 설정을 확인해 주세요.", code="configuration") from None


class VoiceError(Exception):
    pass


def validate_audio(data, filename):
    if not isinstance(data, bytes) or not data or len(data) > 5 * 1024 * 1024:
        raise VoiceError("녹음이 비어 있거나 너무 커요. 1분 이내로 다시 녹음해 주세요.")
    extension = filename.rsplit(".", 1)[-1].lower()
    if extension not in {"wav", "m4a", "mp3", "webm"}:
        raise VoiceError("WAV, M4A, MP3, WebM 음성을 이용해 주세요. 텍스트 입력도 가능해요.")
    if extension == "wav":
        try:
            with wave.open(BytesIO(data)) as audio:
                duration = audio.getnframes() / audio.getframerate()
                if not 0.2 <= duration <= 60:
                    raise VoiceError("녹음은 1분 이내로, 조금 더 또렷하게 말씀해 주세요.")
                frames = audio.readframes(audio.getnframes())
                if not any(frames):
                    raise VoiceError("소리가 들리지 않아요. 마이크를 확인하거나 글로 적어주세요.")
        except (wave.Error, EOFError, ZeroDivisionError):
            raise VoiceError("녹음 파일을 읽지 못했어요. 다시 녹음하거나 글로 적어주세요.") from None
    return extension


def transcribe(data, settings, *, filename="question.wav", client=None):
    extension = validate_audio(data, filename)
    try:
        client = client or make_voice_client(settings)
        response = client.audio.transcriptions.create(
            file=(f"question.{extension}", data), model=settings.stt_model,
            language="ko", response_format="json",
            prompt="한국어 활동 찾기 대화. 사투리와 일상 말투는 의미를 유지해 받아 적습니다. 들리지 않는 내용은 만들지 않습니다.",
        )
        text = response.text
        if not isinstance(text, str) or not text.strip() or len(text) > 1500:
            raise VoiceError("말씀을 정확히 알아듣지 못했어요. 다시 녹음하거나 글로 적어주세요.")
        return text.strip()
    except VoiceError:
        raise
    except AIError:
        raise VoiceError("OpenAI 음성 입력 연결이 설정되지 않았어요. Gemini 질문 이해와 별개예요. 글로 질문해 주세요.") from None
    except Exception:
        raise VoiceError("OpenAI 음성 변환이 지연되거나 실패했어요. 다시 녹음하거나 글로 적어주세요.") from None


def synthesize(text, settings, *, client=None, speed=0.9):
    if speed not in (0.7, 0.9):
        raise VoiceError("지원하지 않는 읽기 속도예요.")
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        raise VoiceError("안내가 비어 있거나 너무 길어요. 화면의 글을 확인해 주세요.")
    try:
        client = client or make_voice_client(settings)
        response = client.audio.speech.create(
            model=settings.tts_model, voice="coral", input=text,
            instructions="한국어로 천천히 또렷하게 읽으세요. 입력 문장을 바꾸거나 정보를 추가하지 마세요.",
            response_format="mp3", speed=speed,
        )
        data = response.read()
        if not isinstance(data, bytes) or not data or len(data) > 8 * 1024 * 1024:
            raise VoiceError("음성을 준비하지 못했어요. 화면의 글을 확인해 주세요.")
        return data
    except VoiceError:
        raise
    except AIError:
        raise VoiceError("OpenAI 음성 안내 연결이 설정되지 않았어요. Gemini와 별개예요. 화면의 글을 확인해 주세요.") from None
    except Exception:
        raise VoiceError("OpenAI 음성 안내를 준비하지 못했어요. 다시 시도하거나 화면의 글을 확인해 주세요.") from None

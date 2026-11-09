"""설정 값은 서버의 환경변수/Secrets에서만 읽는다."""

from dataclasses import dataclass, field
import os


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str = field(default="", repr=False)
    model: str = "gemini-2.5-flash"
    api_key: str = field(default="", repr=False)  # OPENAI_API_KEY: voice only
    stt_model: str = "gpt-transcribe"
    tts_model: str = "gpt-4o-mini-tts"


def load_settings(secrets=None):
    def value(key, default=""):
        for result in (os.environ.get(key), (secrets or {}).get(key), default):
            if isinstance(result, str) and result.strip():
                return result.strip()
        return default

    return Settings(
        gemini_api_key=value("GEMINI_API_KEY"),
        model=value("GEMINI_MODEL", Settings.model),
        api_key=value("OPENAI_API_KEY"),
        stt_model=value("OPENAI_STT_MODEL", Settings.stt_model),
        tts_model=value("OPENAI_TTS_MODEL", Settings.tts_model),
    )

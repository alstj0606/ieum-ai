"""설정 값은 서버의 환경변수/Secrets에서만 읽는다."""

from dataclasses import dataclass, field
import os


@dataclass(frozen=True)
class Settings:
    api_key: str = field(default="", repr=False)
    # Official snapshot ID verified 2026-11-09; access still depends on the project.
    model: str = "gpt-5.4-mini-2026-03-17"
    stt_model: str = "gpt-transcribe"
    tts_model: str = "gpt-4o-mini-tts"


def load_settings(secrets=None):
    def value(key, default=""):
        for result in (os.environ.get(key), (secrets or {}).get(key), default):
            if isinstance(result, str) and result.strip():
                return result.strip()
        return default

    return Settings(
        api_key=value("OPENAI_API_KEY"),
        model=value("OPENAI_MODEL", Settings.model),
        stt_model=value("OPENAI_STT_MODEL", Settings.stt_model),
        tts_model=value("OPENAI_TTS_MODEL", Settings.tts_model),
    )

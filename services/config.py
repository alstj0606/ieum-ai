"""설정 값은 서버의 환경변수/Secrets에서만 읽는다."""

from dataclasses import dataclass, field
import os
import re

GEMINI_API_BASE = "https://generativelanguage.googleapis.com"
GEMINI_API_VERSION = "v1beta"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


class ModelSettingError(ValueError):
    pass


def normalize_model(value):
    if not isinstance(value, str):
        raise ModelSettingError("invalid model setting")
    value = value.strip()
    if value.startswith("models/"):
        value = value[len("models/"):]
    if not re.fullmatch(r"gemini-[a-z0-9][a-z0-9._-]{0,99}", value):
        raise ModelSettingError("invalid model setting")
    return value


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str = field(default="", repr=False)
    model: str = field(default=DEFAULT_GEMINI_MODEL, repr=False)
    model_source: str = "default"
    api_key: str = field(default="", repr=False)  # OPENAI_API_KEY: voice only
    stt_model: str = "gpt-transcribe"
    tts_model: str = "gpt-4o-mini-tts"


def load_settings(secrets=None):
    def value(key, default=""):
        for result in (os.environ.get(key), (secrets or {}).get(key), default):
            if isinstance(result, str) and result.strip():
                return result.strip()
        return default

    model, model_source = DEFAULT_GEMINI_MODEL, "default"
    for source, candidate in (("environment", os.environ.get("GEMINI_MODEL")),
                              ("secrets", (secrets or {}).get("GEMINI_MODEL"))):
        if candidate is None or (isinstance(candidate, str) and not candidate.strip()):
            continue
        model = candidate.strip() if isinstance(candidate, str) else "__invalid_model_setting__"
        model_source = source
        break
    return Settings(
        gemini_api_key=value("GEMINI_API_KEY"),
        model=model, model_source=model_source,
        api_key=value("OPENAI_API_KEY"),
        stt_model=value("OPENAI_STT_MODEL", Settings.stt_model),
        tts_model=value("OPENAI_TTS_MODEL", Settings.tts_model),
    )

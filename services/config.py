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
    search_api_key: str = field(default="", repr=False)  # Brave, server-side only
    tavily_api_key: str = field(default="", repr=False)
    search_provider: str = "tavily"
    allow_paid_search: bool = False
    gemini_key_source: str = "unspecified"
    gemini_key_environment_present: bool = False
    gemini_key_secrets_present: bool = False
    gemini_key_conflict: bool = False
    model_setting_conflict: bool = False

    @property
    def search_configured(self):
        return bool(self.tavily_api_key if self.search_provider=="tavily" else self.search_api_key if self.search_provider=="brave" else True)


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
    env_key=os.environ.get('GEMINI_API_KEY');secret_key=(secrets or {}).get('GEMINI_API_KEY')
    env_present=isinstance(env_key,str) and bool(env_key.strip())
    secret_present=isinstance(secret_key,str) and bool(secret_key.strip())
    conflict=env_present and secret_present and env_key.strip()!=secret_key.strip()
    key_source=('environment' if conflict or env_present and not secret_present else
                'environment_and_secrets' if env_present and secret_present else 'secrets' if secret_present else 'missing')
    env_model=os.environ.get('GEMINI_MODEL');secret_model=(secrets or {}).get('GEMINI_MODEL')
    model_conflict=bool(isinstance(env_model,str) and env_model.strip() and isinstance(secret_model,str) and secret_model.strip() and env_model.strip().removeprefix('models/')!=secret_model.strip().removeprefix('models/'))
    paid_setting=os.environ.get("ALLOW_PAID_SEARCH",(secrets or {}).get("ALLOW_PAID_SEARCH",False))
    return Settings(
        search_api_key=value("BRAVE_SEARCH_API_KEY"),
        tavily_api_key=value("TAVILY_API_KEY"),
        search_provider=value("SEARCH_PROVIDER", "tavily").lower(),
        allow_paid_search=paid_setting is True or (isinstance(paid_setting,str) and paid_setting.strip().lower()=="true"),
        gemini_api_key=value("GEMINI_API_KEY"),
        model=model, model_source=model_source,
        gemini_key_source=key_source,gemini_key_environment_present=env_present,
        gemini_key_secrets_present=secret_present,gemini_key_conflict=bool(conflict),model_setting_conflict=model_conflict,
        api_key=value("OPENAI_API_KEY"),
        stt_model=value("OPENAI_STT_MODEL", Settings.stt_model),
        tts_model=value("OPENAI_TTS_MODEL", Settings.tts_model),
    )

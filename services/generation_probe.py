"""Explicit fixed-prompt A/B probe. No real conversation or response body in results."""
from google.genai import types

from services.ai import AIError, make_client, extract_conditions, generation_text
from services.config import normalize_model, ModelSettingError, GEMINI_API_BASE, GEMINI_API_VERSION
from services.diagnostics import classify_error

PROBE_TEXT = '안녕하세요. 한 문장으로 짧게 인사해 주세요.'
COMPARISON_LABELS = {
    'not_run':'아직 생성 점검을 실행하지 않았어요.',
    'simple_failed':'단순 생성도 실패했어요. 구조화 스키마만의 문제라고 볼 근거가 없어요. 구조화 점검은 실행하지 않았어요.',
    'structured_failed':'같은 모델·경로에서 단순 생성은 성공했지만 기존 구조화 추출은 실패했어요. 입력 형식·시스템 지시·스키마·출력 옵션의 차이를 확인해야 하며 스키마 하나를 원인으로 확정하지 않아요.',
    'both_ok':'고정 문장에서는 두 생성 요청이 성공했어요. 실제 사용자 질문이 해결됐다는 뜻은 아니며 대화 내용·시점에 따른 차이는 아직 미확인이에요.',
}


def inspect_generation(settings, activities, *, client=None):
    report = {'model':None, 'api_base':GEMINI_API_BASE, 'api_version':GEMINI_API_VERSION,
              'path':None, 'simple_code':'not_run', 'structured_code':'not_run',
              'comparison':'not_run', 'free_tier':'not_verified'}
    try:
        model = normalize_model(settings.model)
        report['model'] = model
        report['path'] = f'/{GEMINI_API_VERSION}/models/{model}:generateContent'
    except ModelSettingError:
        report.update(simple_code='model_config',comparison='simple_failed')
        return report
    owned = client is None
    try:
        client = client or make_client(settings)
    except AIError as error:
        report.update(simple_code=error.code,comparison='simple_failed')
        return report
    try:
        try:
            # No schema or system instruction; same model/client/host/version as extraction.
            response = client.models.generate_content(
                model=model, contents=PROBE_TEXT,
                config=types.GenerateContentConfig(
                    max_output_tokens=256,
                    thinking_config=types.ThinkingConfig(thinking_budget=0)
                    if model == 'gemini-2.5-flash' else None,
                ),
            )
            generation_text(response)  # Check completion only; do not keep or show the text.
            del response
            report['simple_code'] = 'ok'
        except AIError as error:
            report.update(simple_code=error.code,comparison='simple_failed')
            return report
        except Exception as error:
            report.update(simple_code=classify_error(error),comparison='simple_failed')
            return report
        try:
            # Production extraction, but a new empty context and fixed non-personal utterance.
            extract_conditions(PROBE_TEXT, {'conditions':{},'pending':None,'history':[]},
                               activities, settings, client=client)
            report.update(structured_code='ok',comparison='both_ok')
        except AIError as error:
            report.update(structured_code=error.code,comparison='structured_failed')
        except Exception as error:
            report.update(structured_code=classify_error(error),comparison='structured_failed')
    finally:
        if owned:
            try:
                client.close()
            except Exception:
                pass
    return report

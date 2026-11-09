"""Explicit, bounded metadata requests. Never generate content or infer free quota."""
import os

from services.ai import make_client, AIError
from services.config import normalize_model, ModelSettingError, GEMINI_API_BASE, GEMINI_API_VERSION
from services.diagnostics import classify_error

SOURCE_LABELS = {'default':'기본값', 'secrets':'Streamlit Secrets', 'environment':'환경변수'}
STATUS_LABELS = {
    'not_checked':'미확인', 'model_config':'모델 설정 형식 확인 필요',
    'metadata_ok':'설정 모델의 정보 조회 성공 · 생성 성공을 뜻하지 않음',
    'method_unsupported':'조회한 메타데이터에 generateContent 지원이 표시되지 않음',
    'list_ok':'첫 페이지 모델 목록 조회 성공 · 무료 한도는 미확인',
}


def inspect_models(settings, *, client=None):
    report = {'model':None, 'model_source':SOURCE_LABELS.get(settings.model_source,'설정 출처 확인 필요'),
              'api_base':GEMINI_API_BASE, 'api_version':GEMINI_API_VERSION,
              'model_setting':'ok', 'metadata_code':'not_checked', 'list_code':'not_checked',
              'generate_content_supported':None, 'models':[], 'first_page_only':True,
              'free_tier':'not_verified', 'generation':'not_tested',
              'custom_base_ignored':bool(os.environ.get('GOOGLE_GEMINI_BASE_URL'))}
    try:
        report['model'] = normalize_model(settings.model)
    except ModelSettingError:
        report['model_setting'] = 'model_config'
    owned = client is None
    try:
        client = client or make_client(settings)
    except AIError as error:
        report['metadata_code'] = report['list_code'] = error.code
        return report
    try:
        if report['model']:
            try:
                metadata = client.models.get(model=report['model'])
                actions = metadata.supported_actions
                if isinstance(actions,list):
                    report['generate_content_supported'] = 'generateContent' in actions
                report['metadata_code'] = 'method_unsupported' if report['generate_content_supported'] is False else 'metadata_ok'
            except Exception as error:
                report['metadata_code'] = classify_error(error,operation='model_get')
        try:
            # One page only; never iterate the Pager (which could issue more requests).
            pager = client.models.list(config={'page_size':50})
            for model in pager.page[:50]:
                try:
                    model_id = normalize_model(model.name)
                except ModelSettingError:
                    continue
                if isinstance(model.supported_actions,list) and 'generateContent' in model.supported_actions:
                    report['models'].append(model_id)
            report['models'] = sorted(set(report['models']))
            report['list_code'] = 'list_ok'
        except Exception as error:
            report['list_code'] = classify_error(error,operation='model_list')
    finally:
        if owned:
            try:
                client.close()
            except Exception:
                pass
    return report

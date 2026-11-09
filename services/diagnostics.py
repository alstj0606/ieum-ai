"""Allowlisted diagnostic labels only; never retain provider bodies or identifiers."""
DIAGNOSTICS = {
    'key_missing': 'Gemini 질문 이해 키가 없어요. 서버의 GEMINI_API_KEY 설정을 확인해 주세요.',
    'configuration': 'SDK 또는 서버 연결 설정을 확인해 주세요.',
    'authentication': 'API 인증이 거부됐어요. 서버의 키 설정을 확인해 주세요.',
    'permission': 'API 사용 권한이 거부됐어요. 프로젝트 권한을 확인해 주세요.',
    'quota': '결제 또는 사용 한도 오류로 분류됐어요. API 결제·한도를 확인해 주세요.',
    'rate_limit': 'Gemini 무료 사용량 또는 요청 한도에 도달했어요. AI Studio에서 프로젝트 한도를 확인해 주세요.',
    'model_config': 'GEMINI_MODEL 형식이 올바르지 않아요. 모델 ID만 설정해 주세요. 원래 설정 값은 표시하지 않아요.',
    'generation_not_found': '생성 요청이 HTTP 404로 끝났어요. 모델 이름·메서드·API 경로·접근 가능 여부 중 어느 원인인지는 아직 확인되지 않았어요. 보조 메뉴의 Gemini 모델 연결 점검을 이용해 주세요.',
    'model_metadata_not_found': '설정 모델의 정보 조회가 HTTP 404예요. 오타·종료·이 API 버전에서의 가용성·접근 문제를 아직 구분하지 못했어요.',
    'model_list_not_found': '모델 목록 조회가 HTTP 404예요. 특정 모델명과 무관한 목록 요청이므로 API 경로·서비스 연결을 확인해 주세요.',
    'non_json_not_found': 'HTTP 404 응답이 Gemini JSON이 아닌 HTML 형식이에요. API 경로 또는 중간 서버 응답을 확인해 주세요. 원문은 표시하지 않아요.',
    'model_access': '모델 또는 API 경로를 사용할 수 없어요. GEMINI_MODEL·접근 권한·서버 주소를 확인해 주세요.',
    'request_schema': '구조화 출력 스키마가 거부됐어요. 서버의 요청 형식을 확인해 주세요.',
    'request_parameter': '요청 설정이 거부됐어요. 모델의 지원 옵션을 확인해 주세요.',
    'request': 'API 요청이 거부됐어요. 서버의 요청 설정을 확인해 주세요.',
    'timeout': 'AI 응답 대기 시간이 지났어요.',
    'connection': 'AI 서버에 연결하지 못했어요.',
    'service': 'AI 서비스에서 오류가 발생했어요.',
    'output_limit': '출력 토큰 한도로 답변이 끝나지 않았어요.',
    'incomplete': 'AI 답변이 끝까지 도착하지 않았어요.',
    'refused': 'AI가 조건 이해 요청에 답하지 않았어요.',
    'response_format': 'AI 답변의 형식이나 조건 값을 검증하지 못했어요.',
    'unknown': '실패 유형을 확인하지 못했어요. 서버 설정과 서비스 상태를 확인해 주세요.',
}


def classify_error(error, *, operation="generate"):
    from google.genai import errors
    import httpx2
    if isinstance(error, (TimeoutError, httpx2.TimeoutException)):
        return 'timeout'
    if isinstance(error, httpx2.TransportError):
        return 'connection'
    if isinstance(error, errors.APIError):
        # Never parse message text; only known structured reason symbols may inform auth.
        details = error.details
        reasons = []
        if isinstance(details, dict):
            nested = details.get('error', details)
            if isinstance(nested, dict) and isinstance(nested.get('details'), list):
                reasons = [item.get('reason') for item in nested['details'] if isinstance(item, dict)]
        if error.code == 401 or 'API_KEY_INVALID' in reasons:
            return 'authentication'
        if error.code == 403:
            return 'permission'
        if error.code == 429:
            return 'rate_limit'  # Cannot infer RPM/TPM/daily/free quota from 429 alone.
        if error.code == 404:
            response = error.response
            content_type = response.headers.get('content-type', '') if response is not None else ''
            if isinstance(content_type, str) and 'text/html' in content_type.lower():
                return 'non_json_not_found'
            return {'model_get':'model_metadata_not_found', 'model_list':'model_list_not_found'}.get(
                operation, 'generation_not_found')
        if error.code >= 500:
            return 'service'
        if error.code == 400:
            return 'request'
    return 'unknown'

"""Allowlisted diagnostic labels only; never retain provider bodies or identifiers."""
DIAGNOSTICS = {
    'key_missing': 'API 키 설정이 없어요. 서버의 OPENAI_API_KEY 설정을 확인해 주세요.',
    'configuration': 'SDK 또는 서버 연결 설정을 확인해 주세요.',
    'authentication': 'API 인증이 거부됐어요. 서버의 키 설정을 확인해 주세요.',
    'permission': 'API 사용 권한이 거부됐어요. 프로젝트 권한을 확인해 주세요.',
    'quota': '결제 또는 사용 한도 오류로 분류됐어요. API 결제·한도를 확인해 주세요.',
    'rate_limit': '요청 한도에 도달했어요. 잠시 후 다시 시도해 주세요.',
    'model_access': '모델 또는 API 경로를 사용할 수 없어요. 모델 ID·접근 권한·서버 주소를 확인해 주세요.',
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


def classify_error(error):
    # Inspect typed SDK exceptions and allowlisted codes only, never str(error)/body.
    from openai import (APITimeoutError, APIConnectionError, AuthenticationError,
                        PermissionDeniedError, APIStatusError, APIResponseValidationError)
    if isinstance(error, (APITimeoutError, TimeoutError)):
        return 'timeout'
    if isinstance(error, APIConnectionError):
        return 'connection'
    if isinstance(error, AuthenticationError):
        return 'authentication'
    if isinstance(error, PermissionDeniedError):
        return 'permission'
    if isinstance(error, APIResponseValidationError):
        return 'response_format'
    if isinstance(error, APIStatusError):
        status, code = error.status_code, error.code
        if status == 401:
            return 'authentication'
        if status == 403:
            return 'permission'
        if status == 402 or (status == 429 and code in {'insufficient_quota','billing_hard_limit_reached'}):
            return 'quota'
        if status == 429:
            return 'rate_limit'
        if status == 404 or code in {'model_not_found','unsupported_model'}:
            return 'model_access'
        if code == 'invalid_json_schema':
            return 'request_schema'
        if code in {'unsupported_parameter','unsupported_value'}:
            return 'request_parameter'
        if status >= 500:
            return 'service'
        return 'request'
    return 'unknown'

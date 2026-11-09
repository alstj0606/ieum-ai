# 모델 조회는 성공하지만 generateContent가 404일 때

확인일: 2026-11-09 (한국 시간). PR #7 병합 후 main `ff6b2f3`에서 `fix/gemini-generation-probe` 생성.

## 확인된 사실과 미확인 사항

사용자 배포 관찰은 metadata_ok/list_ok 성공, 실제 질문의 generation_not_found(HTTP404)다. 개발 환경에서 이 프로젝트를 직접 조회한 결과는 아니다.

현재 main 코드의 기본값과 실제 설치 SDK 3.0.0을 확인했다.

```text
base_url  = https://generativelanguage.googleapis.com
api_version = v1beta
model = gemini-2.5-flash
POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent
```

`models/` 접두어 정규화 이후 SDK가 구성하는 URL을 실제 SDK + MockTransport로 캡처했다. 단순/구조화 요청 모두 동일한 POST 주소이며 `/v1beta/v1beta`나 `/models/models` 중복이 없다. 서버 주소·API 버전 환경변수에 다른 값을 넣어도 명시적 설정이 우선했다. [공식 generateContent API 정의](https://ai.google.dev/api/generate-content?hl=en)의 경로와 [공식 SDK](https://github.com/googleapis/python-genai) 설정 방식에도 부합한다. 공식 자료는 접근 가능한 공식 검색 인덱스/SDK 자료로 대조했다.

따라서 현재까지 **경로 조합이 잘못됐다는 증거는 없다.** 모델 조회 성공만으로 같은 프로젝트의 생성 경로·메서드·시점별 서비스 가용성까지 확인한 것은 아니다. 실제 배포의 404 원인은 아직 미확정이며, 스키마·프로젝트 권한·모델 가용성·서비스 문제 중 하나라고 단정하지 않는다.

**실제 Google API의 단순 생성은 실행하지 못했다.** 이 개발 환경에는 실제 Gemini 키가 없고 Google API 도메인도 허용되지 않는다. 이 PR은 실제 연결을 해결했다는 주장이 아니라 원인을 구분할 수 있는 재현/진단 보완이다.

## 배포 후 선택적으로 실행할 진단

**＋ 보조 메뉴 → Gemini 생성 요청 점검 → 고정 인사말로 생성 점검**을 누른다.

- 사용자 대화·음성 대신 고정 문장 ‘안녕하세요. 한 문장으로 짧게 인사해 주세요.’만 사용한다.
- 1단계는 스키마와 시스템 지시가 없는 텍스트 생성이다. 2.5 Flash에서 기존과 같은 thinking budget 0, 출력 한도 256을 사용한다.
- 1단계가 정상 완료되고 비어 있지 않은 텍스트를 반환할 때만 2단계를 실행한다. 원문은 버리고 성공 코드만 남긴다.
- 2단계는 **기존 extract_conditions 그대로** 호출하되 이력·조건이 비어 있는 새 문맥과 동일 고정 문장을 사용한다. 사용자 세션의 발화·조건을 복사하지 않는다. 공개 활동 종류/태그 외에 개인정보를 추가하지 않는다.
- 생성은 최대 두 번이며 API 사용량이 발생한다. 단순 실패 후에는 구조화 호출을 건너뛴다. 자동 재시도·자동 실행·자동 모델 전환은 없다.
- 응답 원문, 조건 추출 결과, 원본 오류·키·헤더·요청 ID는 보고서/화면/로그에 넣지 않는다. 모델과 요청 대상, 고정 결과 코드, 비교 안내만 세션에 남긴다. 기존 채팅의 질문·대화·검색 결과는 변경하지 않는다.

## 결과 해석

| 결과 | 해석 |
| --- | --- |
| 단순 generation_not_found / 구조화 not_run | 스키마 없는 생성도 404다. 스키마만의 원인이라고 볼 수 없으며 경로/모델/생성 메서드/프로젝트·서비스 가용성은 아직 미확인 |
| 단순 ok / 구조화 generation_not_found | 같은 모델·URL의 단순 생성은 성공했다. 아래 요청 차이에 따른 구분은 되지만 JSON Schema 하나가 원인이라고 확정할 수 없음 |
| 단순 ok / 구조화 response_format | HTTP404와 다르다. 응답 JSON/조건 검증을 통과하지 못한 것 |
| 단순 output_limit/refused 등 | 단순 생성의 정상 완료가 확인되지 않았다. 구조화 단계는 실행하지 않으며 404와 구분 |
| 둘 다 ok | 고정 문장에서는 두 생성이 성공했다. 실제 사용자 질문과 대화 맥락·시점까지 해결된 것은 아님 |

모델 메타데이터 조회나 이 고정 문장 성공은 무료 자격/잔여량을 보장하지 않는다.

## 단순 생성과 기존 조건 추출의 차이

| 항목 | 단순 생성 | 기존 조건 추출 |
| --- | --- | --- |
| 모델·호스트·API 버전·HTTP 경로 | 동일 | 동일 |
| contents | 고정 인사말 문자열 | 현재 발화·빈 조건/이력·공개 종류/태그를 담은 JSON 문맥 |
| system_instruction | 없음 | 기존 조건 추출 PROMPT |
| response_mime_type / response_json_schema | 없음 | application/json / 기존 SCHEMA |
| max_output_tokens | 256 | 2000 |
| temperature | SDK/모델 기본값 | 0 |
| 2.5 Flash thinking budget | 0 | 0 |
| 도구/자동 함수 호출 | 도구 없음 | 도구 없음, 자동 함수 호출 명시적 비활성화 |

여러 차이가 있으므로 단순 성공/구조화 실패만으로 특정 옵션 하나를 제거하거나 스키마를 완화하지 않는다. 실제 결과를 확인한 다음 추가로 한 변수씩 비교해야 한다.

## 변경 범위와 검증

- `services/config.py`, make_client, 기존 구조화 GenerateContentConfig, SCHEMA·조건 검증은 그대로 유지했다. 요청 설정 AST 비교도 수행했다. 오류를 숨기려고 모델·API 버전·스키마를 바꾸지 않았다.
- `services/ai.py`의 기존 완료/거절/텍스트 유효성 검사를 generation_text 공통 함수로 분리해 진단과 운영 요청이 같은 기준을 사용한다.
- `services/generation_probe.py`와 보조 메뉴 진단만 추가했다. 기본 UI/마이크 전환·공식 데이터·대체 검색·대화·음성은 유지했다.
- unittest **83개 통과**: 기존 75개 + 단순404의 1회 종료, 단순성공/구조화404, 둘 다 성공 시 원문 미보관, 토큰한도/거절/형식, 키없음/잘못된모델 무호출, 자원 정리, 실제 SDK의 정확한 두 URL·요청 차이·환경변수 우선순위, 점검 후 기존 대화 보존 8개.
- Chromium/Playwright **13개 흐름**: 기존 12개와 고정 인사말 성공/구조화404 비교·응답 원문 미노출·기존 대화 보존 추가. 모의 STT/TTS와 320/390/768px 기존 UI 회귀 포함.
- 모의 서버가 의도적으로 단순 생성은 성공, 고정 인사말의 구조화 추출은 404를 반환한다. 실제 Google의 동작이나 스키마 오류를 재현했다고 주장하지 않는다.
- 실제 Gemini/Community Cloud 수정본 배포/iPad Safari 등 실기기는 미검증이다. 실호출에 근거한 해결 확인은 아직 없다.

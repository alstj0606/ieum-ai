# Gemini 질문 이해 전환과 배포 설정

확인일: 2026-11-09 (한국 시간). 최신 main `50a74a7`에서 `feat/gemini-intent-extraction` 생성.

## Streamlit Community Cloud Secrets

앱의 Settings → Secrets에 다음을 최상위 항목으로 입력한다. 실제 키는 Git이나 채팅에 넣지 않는다.

```toml
GEMINI_API_KEY = "직접 발급받은 Gemini API 키"
GEMINI_MODEL = "gemini-2.5-flash"
```

`GEMINI_MODEL`은 선택이며 생략/공백이면 `gemini-2.5-flash`다. 환경변수의 유효한 문자열이 같은 이름의 Secrets보다 우선한다. 키는 `GEMINI_API_KEY`에서만 읽으며 `GOOGLE_API_KEY`나 `OPENAI_API_KEY`로 대신 연결하지 않는다. Vertex AI/Enterprise 인증 경로는 사용하지 않는다.

기존 `OPENAI_MODEL`은 질문 이해에 더 이상 사용하지 않는다. Gemini가 실패해도 OpenAI LLM으로 자동 전환하거나 유료 기능을 추가 호출하지 않는다.

### 음성은 별도 설정

이번 작업은 질문 의도/조건 추출만 전환했다. 기존 STT/TTS는 **OpenAI**이며 Gemini 키와 무료 한도로 동작하지 않는다. 다음 설정은 기존 음성을 계속 사용할 때만 필요하다.

```toml
# 선택: OpenAI 음성 API를 계속 사용할 경우만 설정
OPENAI_API_KEY = "음성용 OpenAI API 키"
OPENAI_STT_MODEL = "gpt-transcribe"
OPENAI_TTS_MODEL = "gpt-4o-mini-tts"
```

Gemini 키만 있어도 **글 질문 → Gemini 조건 이해 → 공식 활동 추천**은 가능하다. OpenAI 키가 없으면 파일 음성 변환/답변 듣기는 비활성화되며, 기본 마이크로 녹음하더라도 STT 연결 안내와 글 입력 대안이 제공된다. OpenAI 잔액이 없으면 STT/TTS는 실패할 수 있다. 화면의 인사와 이용 안내에 공급자를 명시했다. 브라우저 기반 무료 STT/TTS는 이번에 구현하지 않았다.

## 무료 티어·공식 자료 확인

- [공식 가격표](https://ai.google.dev/gemini-api/docs/pricing): 검색 인덱스에서 `Gemini 2.5 Flash`/`gemini-2.5-flash`의 Standard 입력·출력 Free Tier 항목이 무료로 표시된 것을 확인했다. 무료 티어가 존재한다는 의미이며, 사용자 프로젝트의 사용 가능 여부나 잔여량을 확인한 것은 아니다.
- [공식 모델 문서](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash): 공식 검색 결과에서 모델 ID와 Structured outputs 지원을 확인했다.
- [공식 한도 안내](https://ai.google.dev/gemini-api/docs/rate-limits): 한도는 프로젝트/티어 등에 따라 달라지며 AI Studio에서 실제 수치를 확인한다. 코드에서 무료 티어를 강제하는 설정은 없다. 연결할 Google 프로젝트의 Free Tier/결제 상태·모델 접근·RPM/TPM/RPD를 AI Studio에서 확인한다. 결제가 활성화된 프로젝트의 비용이 항상 0이라고 보장하지 않는다.
- [공식 구조화 출력 문서](https://ai.google.dev/gemini-api/docs/structured-output)와 [Google 공식 Python SDK](https://github.com/googleapis/python-genai)의 `response_json_schema`, `GenerateContentConfig`, 클라이언트 종료 사용법을 확인했다.
- [Thinking 안내](https://ai.google.dev/gemini-api/docs/generate-content/thinking?hl=en)의 2.5 계열 thinking budget 방식을 참고하고 `gemini-2.5-flash`에만 budget 0을 사용한다. 다른 모델을 설정하면 이 옵션은 자동 적용하지 않는다.

문서 접근 한계: ai.google.dev의 가격표/모델/구조화 출력 페이지 본문 일부는 도구에서 text/markdown 미지원 또는 aistudio.google.com 리디렉션 접근 오류가 발생했다. 가격/모델/한도는 **공식 검색 인덱스의 본문 발췌**, SDK 사용법은 **접근 가능한 공식 GitHub 문서와 설치된 실제 SDK**로 대조했다. Google 계정 대시보드나 프로젝트 할당량을 직접 확인하지 않았다. 무료 티어의 데이터 활용 조건도 공식 가격표/약관을 확인한다. 현재 공식 가격표 검색 결과는 무료 티어 입력이 제품 개선에 사용될 수 있다고 안내한다.

## 구현과 정보 경계

- `google-genai==3.0.0` 공식 SDK를 추가·고정했다. 기존 `streamlit==1.66.1`, `openai==3.46.0`은 유지했다. Python 3.12에서 의존성 설치와 pip check를 확인했다.
- `services/ai.py`: Gemini Developer API `v1beta`, `client.models.generate_content`, JSON 응답/동일 SCHEMA, 출력 2,000토큰, temperature 0, timeout 30,000ms, 전체 시도 1회(자동 재시도 없음). 자동 함수 호출을 끄고 도구·검색 grounding·파일·음성·이미지 기능은 보내지 않는다. 소유한 SDK 클라이언트는 성공/실패 후 닫는다.
- 기존 FIELDS·SCHEMA·PROMPT·validate_extraction을 유지했다. program name/가격/전화/URL/접수 상태를 출력 필드에 추가하지 않았다. 기존 조건·pending·최근 이력·활동 종류/태그와 새 질문만 제공하며, 활동 정보/카드는 기존 Python/공식 JSON이 결정한다. 서버가 스키마의 모든 제약을 강제한다고 가정하지 않고 동일 로컬 검증을 적용한다.
- `services/config.py`: Gemini와 OpenAI 음성 키는 서로 다른 repr=false 필드다. 어느 키도 다른 공급자로 보내지 않는다.
- `services/voice.py`: 이전 OpenAI 클라이언트 생성을 `make_voice_client`로 분리했다. STT/TTS API 방식·모델 기본값·검증은 유지하고 공급자를 오류 문구에도 명시했다.
- `services/diagnostics.py`: Gemini SDK 타입/HTTP 코드와 허용된 구조화 심볼만 확인한다. 401/API_KEY_INVALID → authentication, 403 → permission, 429 → rate_limit, 404 → model_access, 400 → request, 5xx → service, 전송 timeout/connection과 응답 거절/한도/형식 실패를 구분한다. 429만으로 분당 제한/일일 무료량/결제 문제를 확정하지 않는다. 오류 원문·상세·키·질문·음성을 저장/로그 출력하지 않는다.
- `services/dialogue.py`: mode=gemini로 표시하며 기존 조건 누적·수정·후속 질문·신청 안내와 오류 시 공식 키워드 대체 검색을 유지한다. 프로그램 사실은 생성하지 않는다.
- `ui/chat.css`·`ui/chat.js`, 공식 활동 데이터 10건과 출처, 검색/추천 모듈은 변경하지 않았다. 단일 채팅 입력과 마이크/전송 전환도 유지했다. 공급자 안내 문구만 추가했다.

## 테스트와 미검증

- unittest **66개 통과**: 기존 62개를 Gemini 계약/오류 타입에 맞춰 갱신하고 Gemini 키만 있는 글 질문, OpenAI 키만으로 Gemini 미호출, 소유 클라이언트 종료, 실제 SDK의 모의 HTTP 전송/원래 스키마 보존/키 분리 4개를 추가했다. 기존 검색·조건 누적·추가 질문·수정·오류 대체·사실 경계·STT/TTS 검사를 유지했다.
- Chromium/Playwright **10개 흐름**: 320/390/768px 기존 채팅·버튼 전환·카드·신청 안내, 실제 Google SDK→로컬 모의 generateContent, 모의 429→안전한 진단/공식 대체 검색/후속 질문, OpenAI 모의 STT/TTS 연결·재생/중지·수정·재녹음, 권한/장치/미지원·재생 실패·파일 업로드를 검사했다.
- Google 모의 출력은 제한적 키워드 처리 결과이며 실제 Gemini 이해 품질 검사가 아니다. 모의 OpenAI STT는 고정 문장, TTS는 시험용 톤이다. 제보 질문에 의도적으로 Gemini 429를 반환한다. 실제 프로젝트가 무료 한도 초과라는 진단이 아니다.
- **실제 Gemini 호출 미실시**: 개발 환경에 GEMINI_API_KEY가 없고 generativelanguage.googleapis.com도 네트워크 허용 목록에 없다. 사용자 키의 모델 접근·무료 잔여량·실제 스키마 수락/한국어 이해는 미검증이다.
- 실제 OpenAI 음성 호출, iPad/iPhone Safari·Android Chrome 실기기, Community Cloud 새 브랜치 배포는 미검증이다.

## 배포 후 확인

1. PR 검토·병합 후 Community Cloud에서 requirements 재설치/재시작을 확인하고 위 Gemini Secrets를 설정한다.
2. ‘강서구에서 어르신이 참여할 수 있는 운동을 추천해줘’를 글로 입력한다. 연결 상태 진단이 없고 공식 카드가 나오는지 확인한다. 기본 대체 검색 표시만 나오면 Gemini 호출 성공으로 간주하지 않는다.
3. ‘오전 말고 오후요’, ‘상관없어요’, ‘신청 방법 알려줘’로 조건 누적·변경을 확인한다. 결과가 없거나 자격 미확인인 경우를 정상적으로 구분하는지도 확인한다.
4. 실패하면 ‘연결 상태 확인’의 고정 코드만 확인하고 AI Studio의 프로젝트 사용량·한도·키/모델 권한을 점검한다. 키/원본 오류는 공개하지 않는다.
5. 모의 테스트 전용 `GOOGLE_GEMINI_BASE_URL`, `OPENAI_BASE_URL`은 실제 배포에 설정하지 않는다. 음성은 별도 OpenAI 설정/잔액이 있어야 검증할 수 있다.

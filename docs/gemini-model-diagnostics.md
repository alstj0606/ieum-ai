# Gemini model_access / 404 점검

> 모델 조회는 성공하나 생성만 실패하는 경우의 추가 진단은 [단순/구조화 생성 비교](gemini-generation-probe.md)를 따른다. 아래 모델 정보 확인 버튼은 계속 읽기 전용이며 새 생성 점검 버튼과 구분된다.

확인일: 2026-11-09 (한국 시간). PR #6 병합 후 main `c954065`에서 `fix/gemini-model-diagnostics` 생성.

## 확인된 사실

- 기존 PR #6의 기본 모델은 `gemini-2.5-flash`, 버전은 `v1beta`, SDK는 `google-genai==3.0.0`, 방식은 `client.models.generate_content`였다. GEMINI_MODEL이 없거나 빈 문자열/공백이면 기본값을 쓴다. 유효한 환경변수가 Secrets보다 우선한다.
- 이전 분류기는 Google SDK APIError의 HTTP 코드가 404이면 본문이나 작업 종류에 상관없이 모두 `model_access`로 표시했다. 사용자 화면의 이 코드만으로 모델명 오류·종료·메서드 미지원·프로젝트 접근·API 경로 문제를 확정할 수 없다.
- [공식 모델 문서](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash)의 검색 결과에는 모델 ID와 Structured outputs 지원이 명시되어 있다. [공식 생성 API](https://ai.google.dev/api/generate-content?hl=en) 및 [공식 SDK](https://github.com/googleapis/python-genai)와 비교하면 이 모델명/호출 방식이 명백히 틀렸다는 근거는 없다. 실제 계정의 모델 가용성은 별개다.
- SDK는 base_url을 지정하지 않으면 `GOOGLE_GEMINI_BASE_URL` 등의 기본 주소 설정을 사용할 수 있었다. 이것이 실제 배포에 설정되었는지는 확인하지 못했다.
- 이 개발 환경에는 실제 Gemini 키가 없고 Google API 도메인 네트워크도 허용되지 않는다. 사용자의 Cloud Secrets/환경변수, 원본 응답, 모델 목록, 무료 한도를 직접 조회하지 않았다.

## 수정 후 실제 요청 설정

```text
POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent
```

SDK `HttpOptions`에 공식 base_url과 api_version을 명시한다. `GOOGLE_GEMINI_BASE_URL`이 있어도 실제 앱의 요청 주소를 바꾸지 않는다. 요청 URL을 재현하는 테스트에서는 실제 Google SDK와 모의 HTTP 전송을 사용해 위 URL과 일치함을 검증했다. 모델을 바꾸면 경로의 모델 ID만 바뀐다.

키는 기존처럼 GEMINI_API_KEY 환경변수 또는 Streamlit Secrets에서 읽고 SDK가 헤더로 전달한다. 키를 URL 쿼리에 넣거나 화면/로그에 표시하지 않는다. 현재 설정은 다음과 같다.

```toml
GEMINI_API_KEY = "직접 발급받은 키"
GEMINI_MODEL = "gemini-2.5-flash"
```

- GEMINI_MODEL 생략/빈 값/공백: 기본 모델 사용.
- `models/gemini-2.5-flash`: 한 번의 `models/` 접두어를 제거해 정규화.
- 전체 URL, 중복 `models/models/`, 따옴표가 값에 포함된 문자열, 잘못된 자료형: 로컬 `model_config`로 분류하고 생성 요청하지 않음. 원래 잘못된 값은 표시하지 않는다.
- `gemini-typo`처럼 모델 ID 모양은 맞지만 실제로 없는 이름: 로컬에서 존재를 단정하지 않음. 메타데이터 조회/실제 생성으로 확인해야 한다.
- 설정의 출처는 기본값/Secrets/환경변수로 구분한다. 실제 키와 원래 잘못된 설정 문자열은 출력하지 않는다.

## 안전한 404 분류

| 코드 | 관찰된 사실 / 해석 한계 |
| --- | --- |
| model_config | 설정 문법이 잘못됨. API 응답과 무관한 로컬 오류 |
| generation_not_found | generateContent 요청이 404. 모델·메서드·API 버전·접근·서비스 중 어떤 원인인지 미확인 |
| model_metadata_not_found | 설정 모델의 GET 정보 조회가 404. 오타·종료·이 API에서의 가용성·접근을 아직 구분 못함 |
| model_list_not_found | GET 모델 목록 요청이 404. 이 요청에는 특정 모델 ID가 없으므로 특정 모델명 탓으로 단정하지 않음 |
| non_json_not_found | 404 응답의 Content-Type이 HTML. Gemini JSON 응답이 아니므로 API 경로/중간 서버 확인 필요. 어느 서버가 원인인지는 미확인 |
| permission | 실제 HTTP 403 접근 거부. 404와 구분하지만 모델만의 권한 문제라고 단정하지 않음 |

인증·429·연결·timeout·응답 형식 분류와 공식 데이터 기반 대체 검색은 유지한다. 원본 오류/본문/헤더/요청 ID/키/사용자 질문/음성을 새 진단에 저장하거나 로그 출력하지 않는다. 오래된 세션의 model_access 안내는 유지하지만 새 404는 작업별 코드로 표시한다.

## 배포 후 안전하게 확인하는 방법

1. 이 PR 반영·재배포 후 **＋ 보조 메뉴 → Gemini 모델 연결 점검 → 모델 정보 확인**을 누른다. 자동 실행하지 않는다.
2. 유효한 설정 모델 ID, 설정 출처, 고정 공식 주소·버전과 모델 정보/목록의 별도 상태를 확인한다.
3. 모델 정보 조회와 목록 조회만 한다. 최대 2회의 읽기 요청, 목록은 첫 페이지 최대 50개이며 자동으로 다음 페이지를 읽지 않는다. 질문/음성이나 생성 프롬프트는 보내지 않고 generateContent를 호출하지 않는다. 모델을 자동 교체하지 않는다. 결과는 세션에만 남고 버튼을 다시 누를 때만 다시 조회한다.
4. `metadata_ok`는 메타데이터 조회 성공이며 생성 성공/무료 이용 보장이 아니다. `generateContent`가 지원 메서드에 없으면 method_unsupported로 표시한다. 목록에는 메타데이터상 generateContent 지원이 표시된 Gemini ID만 보인다. 첫 페이지에 없다는 사실만으로 미지원이라고 단정하지 않는다.
5. 같은 Google 프로젝트의 [AI Studio](https://aistudio.google.com/)에서 모델별 무료 자격/실제 한도(RPM·TPM·RPD)와 결제 상태를 확인한다. **Models.get/list 응답에는 무료 잔여량이 없으므로 무료 여부는 항상 미확인으로 표시한다.**
6. [공식 가격표](https://ai.google.dev/gemini-api/docs/pricing)의 검색 결과에 2.5 Flash 및 2.5 Flash-Lite 무료 입력/출력 항목이 있다. 가격표에 있어도 해당 프로젝트에서 활성화되거나 무료량이 남았다는 뜻은 아니다. 실제 목록·프로젝트 한도·가격표를 함께 보고 수동으로 모델 설정을 결정한다.
7. 모델 정보는 성공했는데 질문에서 generation_not_found가 계속되면, 모델명 오타만으로 설명할 수 없다는 추가 증거다. 하지만 생성 메서드/프로젝트 가용성/서비스 오류의 정확한 원인은 여전히 미확인이다. 새 진단 코드와 메타데이터 상태만 공유하고 키·원본 오류는 공유하지 않는다.

문서 접근 한계: Google 일부 본문은 도구의 형식 미지원/리디렉션으로 열지 못했다. 이번 공식 모델·가격·Models API 확인은 공식 검색 인덱스의 본문 발췌와 접근 가능한 SDK 문서/실제 SDK 코드를 함께 사용했다. 실제 프로젝트 무료 모델 목록을 확인했다는 뜻이 아니다.

## 키 없이 재현한 검증

- unittest **75개 통과**: 기존 66개 + 설정 기본값/출처/정규화/오류, 정확한 공식 생성 URL과 환경변수 무시, 404 작업별/HTML/403 분류, 메타데이터 성공≠무료/생성 성공, 별도 조회 실패, 잘못된 모델에서도 목록 조회/자원 정리, 실제 SDK 메타데이터 GET 경로, 404 대체 검색, 점검 후 대화 보존 9개 추가.
- Chromium/Playwright **12개 흐름**: 기존 10개 + 읽기 전용 점검과 대화 유지, 모의 생성 404 후 새 진단/공식 대체 검색. 320/390/768px 채팅·버튼·음성 모의·실패 대안 회귀 포함.
- 실제 Google 계정 호출/무료 한도/Cloud 수정본 배포/iPad Safari 등 실기기는 미검증이다. 모의 metadata=200과 생성=404는 같은 모델에 대해 재현할 수 있지만 실제 프로젝트의 원인이라고 주장하지 않는다.
- 공식 데이터 10건·출처, 검색·추천·음성 서비스, 조건 스키마·검증, 기존 ui/chat.css·chat.js 및 requirements는 변경하지 않았다.

브라우저 모의 검사는 생산 코드의 서버 주소를 바꾸지 않는다. `tests/mock_app.py`에서만 Google 클라이언트를 localhost로 연결한다. **Cloud entrypoint는 계속 app.py이며 mock_app.py를 배포하지 않는다.**

```bash
# API 없는 기본 앱
python -m streamlit run app.py --server.port=18502 --server.headless=true
# 로컬 전용 API 모의 서버
PYTHONPATH=. python tests/mock_voice_server.py
# 가짜 키만 사용하는 브라우저 테스트 전용 앱
GEMINI_API_KEY=local-gemini-mock-only OPENAI_API_KEY=local-openai-mock-only \
OPENAI_BASE_URL=http://127.0.0.1:18503/v1 \
python -m streamlit run tests/mock_app.py --server.port=18504 --server.headless=true
node tests/browser_smoke.cjs
```

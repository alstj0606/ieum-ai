# 이음 AI 대화·음성 구조와 초기 구현 기록

> **최신 UI 안내:** 아래 사용 흐름·화면·50개 테스트 결과는 PR #2의 초기 구현 기록입니다. 현재 채팅형 화면과 최신 검증 결과는 [docs/chat-ui.md](chat-ui.md)를 따릅니다. 모델·Secrets·API 검증 한계 설명은 계속 참고할 수 있습니다.

작업일: 2026-11-09. 작업 브랜치 `data/gangseo-official-activities`.
공식 자료 10건과 가상 수영 JSON, 기존 검색 모듈은 보존했다.
커밋·Push·PR·배포는 하지 않았다.

## 구현 구조와 사용 흐름

1. 텍스트 입력 또는 녹음 후 음성을 글로 바꾼다.
2. 변환된 글을 확인·수정하고 **프로그램 찾아보기**를 누른다.
3. LLM은 의도와 조건만 구조화한다. 지역이 없으면 지역 한 가지만 묻는다.
   양수 예산에 단위가 없으면 회당/월 금액인지 한 가지를 묻는다.
   시간·나이·성별을 무조건 질문하지 않는다.
4. Python이 기존 조건에 새 조건을 반영하고 공식 JSON을 검색한다.
5. 최대 3개 카드와 신청 안내를 보여준다. 실제 신청은 외부 공식 페이지에서 한다.
6. **답변 듣기**는 화면에 공개된 원문만 TTS에 전달한다. 준비 후 ▶로 재생한다.
   일시정지는 기본 재생기, **음성 중지**는 세션 음성을 지우고 재생기를 제거한다.

이력·누적 조건·추가 질문 대상·선택 활동은 `st.session_state`에만 둔다.
최근 20개 발화 중 API에는 최근 10개만 전송한다. 질문 1,500자 제한,
SDK 20초 타임아웃과 자동 재시도 0회로 중복 비용을 줄인다.
입력 위젯 재실행만으로 LLM을 호출하지 않는다. 화면의 고정 선택 버튼은
API 없이 결정된 동작을 수행한다. 새로운 검색·조건 변경 시 이전 재생 음성을 지운다.

### 사실과 AI 응답의 경계

- `services/ai.py`: Responses API의 strict JSON Schema로 의도, 조건 변경,
  해제 필드, 화면 결과의 선택 번호만 받는다. 로컬에서도 타입·허용 키·값을 검증한다.
- 프로그램명·금액·출처·URL·추천 답변 필드는 모델 응답 계약에 없다.
  이런 필드를 추가한 응답은 거부한다. 모델이 만든 링크를 사용하지 않는다.
- `services/dialogue.py`: 한 번에 한 가지 추가 질문, 누적·수정·상관없음,
  결과 선택과 신청 안내를 처리한다. ‘네’는 예약·결제 완료가 아니다.
- `services/recommendations.py`: 기존 검색을 사용하고 대상·초보 학습 목적·예산을
  점검한다. 화면과 음성은 같은 `activity_facts()` 원문을 쓴다.
- `services/voice.py`: 녹음을 STT로 보내거나 확정된 화면 안내문을 TTS로 보낸다.
  원음·API 응답·키를 파일이나 로그에 저장하지 않는다.

### 검색·자격·예산의 한계

- 결과 없음, 마감/활동 종료, 자격 불일치, 접수 미확인/접수 전,
  자료 부족, 예산 초과를 구분한다. 지역 전체에 활동이 없다고 단정하지 않는다.
- 자격 규칙은 기존 JSON에 명시된 40세 이상·여성·거주지·성인·초보 교육 필요
  조건만 별도로 구조화했다. 규칙은 `recommendations.py`의 `RULES`에 있으며
  근거는 원본 데이터의 대상과 주의사항이다. 대상 정보가 추가되면 규칙도 갱신해야 한다.
- 나이로 건강·신체 능력을 추정하지 않는다. 성인 기준을 확정할 수 없는 경우는
  기관 확인 안내를 유지한다. 알려지지 않은 자격을 충족한다고 표시하지 않는다.
- 사용자 거주지와 검색 지역을 구분한다. 모르는 자격은 카드에서 확인을 요청한다.
- 초보 학습 요청에 파크골프장 대관을 강습처럼 추천하지 않는다.
- 예산은 과금 단위를 임의 환산하지 않는다. 무료는 0원으로 검색하며,
  비용 null 또는 월/회당 단위를 대조할 수 없으면 자료 부족으로 분리한다.
- 관심·참여 목적은 소수 자료의 분류/태그를 이용한 간단한 검색이다.
  실제 회차별 빈자리·휴장·추가 접수는 조회하지 않는다.
- API 키가 없으면 `기본 검색 모드`임을 표시한다. 이 모드는 제한적인 키워드와
  고정 버튼만 처리하며 자유로운 자연어 이해나 사투리 인식 성공을 보장하지 않는다.
  **조건을 골라 직접 찾기**는 항상 이용할 수 있다.

## 모델과 API 선택

- SDK: `openai==3.46.0` 고정. 해당 SDK를 가상환경에 설치하고 메서드 서명과
  로컬 모의 HTTP 서버를 통해 직렬화·응답 처리 경로를 점검했다.
- 조건 추출: `gpt-5.4-mini-2026-03-17`, Responses API, strict Structured Outputs,
  reasoning effort low. 조건 추출에 맞는 소형 모델과 고정 스냅샷으로 선택했다.
  실제 계정의 모델 사용 권한·한국어 이해 품질은 API 키로 별도 검증해야 한다.
- STT: `gpt-transcribe`, Audio Transcriptions API, `language="ko"`.
  브라우저 Web Speech Recognition의 엔진·언어 지원 차이에 의존하지 않고
  녹음 파일을 서버에서 처리한다. 사투리를 포함한 원문의 의미 보존을 요청하지만
  실제 인식 품질은 녹음 자료로 아직 검증하지 않았다.
- TTS: `gpt-4o-mini-tts`, Audio Speech API, coral 음성, 한국어 읽기 지시,
  속도 0.9. 재생은 `st.audio(autoplay=False)`로 제공한다.
  **공식 모델 페이지에는 Deprecated 표시가 있다.** 현재 Speech API 가이드에
  기존 통합용으로 안내되는 경로를 사용했으며, 계정에서의 사용 가능 여부와
  종료 일정을 배포 전에 다시 확인해야 한다. 2026-11-09 확인한 Speech API
  레퍼런스에는 **2027-01-06 종료 예정**으로 명시되어 있다. 실패해도 글 안내는 유지한다.
  새 실시간 음성 API로의 전환은 이번 파일 기반 MVP에 포함하지 않았다.
- 모델 설정은 아래 환경변수/Secrets로 바꿀 수 있다. 모델을 바꿀 때에는
  해당 엔드포인트·구조화 출력·음성 파라미터 호환성을 다시 확인해야 한다.

참고한 공식 문서:
[GPT-5.4 Mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini),
[구조화 출력](https://developers.openai.com/api/docs/guides/structured-outputs),
[GPT-Transcribe](https://developers.openai.com/api/docs/models/gpt-transcribe),
[STT](https://developers.openai.com/api/docs/guides/speech-to-text),
[TTS](https://developers.openai.com/api/docs/guides/text-to-speech),
[TTS 모델](https://developers.openai.com/api/docs/models/gpt-4o-mini-tts),
[Streamlit 녹음](https://docs.streamlit.io/develop/api-reference/widgets/st.audio_input).

## 서버 설정

Streamlit Community Cloud의 앱 Settings → Secrets에 설정한다.
실제 키를 README·채팅·코드·Git에 넣지 않는다. 로컬에서는 서버 환경변수로 설정해도 된다.
환경변수가 있으면 Secrets보다 우선한다.

```toml
OPENAI_API_KEY = "<서버 설정 화면에서 실제 API 키 입력>"
OPENAI_MODEL = "gpt-5.4-mini-2026-03-17"
OPENAI_STT_MODEL = "gpt-transcribe"
OPENAI_TTS_MODEL = "gpt-4o-mini-tts"
```

이 문서의 키 문자열은 실제 키가 아닌 자리 표시자다. 개인 API 키를 사용자에게
입력받는 화면은 제공하지 않는다. ChatGPT 구독과 API 이용 요금은 별도다.
프로젝트 API 이용 한도와 사용량을 서버 운영자가 확인해야 한다.
이번 Cloud 환경에는 API 키가 없고 `api.openai.com`도 시작 시 허용 목록에 없다.
Codex Cloud 실호출 시에는 환경 설정에서 해당 도메인을 허용하고 키를 안전하게
연결해야 한다. Community Cloud에서는 앱 Secrets와 외부 통신을 따로 확인한다.

대화 조건 추출에는 `store=False`를 사용한다. 이것이 제공자의 모든 데이터
보존을 없앤다는 의미는 아니다. 음성 변환 버튼의 전송 안내를 확인하고
불필요한 개인정보·건강정보는 질문에 넣지 않도록 사용 안내가 필요하다.

## 모바일·음성의 실제 사용 조건

- HTTPS의 배포 앱 주소를 Safari/Chrome에서 직접 연다. 임베디드 화면에서는
  상위 페이지의 마이크 Permissions Policy 때문에 녹음이 제한될 수 있다.
- 녹음은 Streamlit `st.audio_input`이 담당한다. 브라우저의 마이크 허용이 필요하다.
  거부/장치 없음/미지원 시 네이티브 위젯 안내와 화면의 권한 도움말을 확인하고
  텍스트 또는 음성 파일 업로드로 진행한다.
- WAV 녹음은 1분 이내, 0.2초 이상인지 검사한다. 업로드는 WAV/M4A/MP3/WebM,
  최대 5MiB. 압축 파일의 길이는 서버에서 별도로 디코딩하지 않으므로 파일 크기만
  제한한다. 실제 파일 포맷이 잘못되면 STT 오류 안내로 전환한다.
- 음성 인식 결과는 질문 입력창에만 넣으며 자동 제출하지 않는다.
  사투리·고유명사·숫자가 맞는지 확인하고 고친 뒤 보내야 한다.
- 답변 듣기는 사용자의 버튼 조작 때만 생성한다. 음성 재생기를 ▶로 직접
  재생하며 자동 재생하지 않는다. 재생기 일시정지/음성 중지와 텍스트 안내를 제공한다.
- 한국어 발음·실제 녹음·스피커 출력·iPad Safari·모바일 키보드·Community Cloud는
  실기기 검증이 필요하다. Chromium 화면 크기 에뮬레이션을 Safari 검증으로 간주하지 않는다.

## 테스트 실행

```bash
python -m unittest discover -s tests -v
python -m pip check
```

기존 24개 테스트 항목을 유지했다. 이전 시연 전용 화면 테스트의 ‘어떤 질문이든
가상 결과 표시’ 가정은 공식 검색 연결에 맞게 바꾸고, 빈 질문·예시 카드 필드·
초기화·가상/실제 분리 검증은 유지했다. 실제 유료 API 성공을 뜻하지 않는다.

선택적인 Chromium 브라우저 검사에는 개발 환경의 Playwright와 Chromium이 필요하다.
앱 런타임 패키지에는 Playwright를 추가하지 않는다. 아래는 **로컬 모의 서버** 실행 예다.

```bash
# 터미널 1: API 키 없는 앱
python -m streamlit run app.py --server.port=18502 --server.headless=true
# 터미널 2: 외부 요청 없는 모의 API
PYTHONPATH=. python tests/mock_voice_server.py
# 터미널 3: 모의 서버에만 연결한 앱 (실제 키를 사용하지 말 것)
OPENAI_API_KEY=local-mock-only OPENAI_BASE_URL=http://127.0.0.1:18503/v1 \
  python -m streamlit run app.py --server.port=18504 --server.headless=true
# 터미널 4
node tests/browser_smoke.cjs
```

모의 STT는 고정 문장을 반환하고, 모의 LLM은 기본 키워드 처리 결과를 반환한다.
모의 TTS는 말소리가 아닌 시험용 톤이다. 이 검사는 UI→SDK→HTTP→UI 연결과
재생·중지를 검사하며, 실제 언어 이해·음성 인식·합성 품질은 검사하지 않는다.
`OPENAI_BASE_URL` 모의 설정은 실제 배포에 사용하지 않는다.

### 이번 실행 결과

- unittest **50개 통과**: 기존 24개 항목 + 대화·API 계약/실패·음성·UI 회귀 26개.
- Chromium 브라우저 검사 **7개 흐름 통과**:
  320/390/768px의 키 없는 대화·예시·가로 넘침/64px 버튼 검사 3개,
  모의 STT 파일→수정→SDK 대화→공식 링크→신청 안내→톤 재생/중지 1개,
  마이크 권한 거부 모의 1개, 합성 장치 녹음/중지→모의 STT 1개,
  미디어 API 미지원 모의의 텍스트 대체 경로 1개.
- 입력은 일반 위젯과 명시적인 제출 버튼으로 분리해 녹음 변환 실패 때에도
  작성 중인 글을 보존한다. 녹음 업로드가 준비되기 전에는 변환 버튼을 비활성화한다.
- Python 문법·공백 검사, `pip check`, 공식 데이터 10건의 원문 보존 확인.
- 실제 OpenAI 호출은 **미실시**: API 키 없음. 실제 한국어/사투리 품질과
  TTS 발음, iPad Safari·Community Cloud·실제 사용자 테스트도 미실시.

## 배포 전 남은 검증

1. 실제 API 키로 모델 접근·구조화 응답·한국어와 사투리 STT·TTS를 소수 실호출한다.
2. iPad Safari/실제 스마트폰에서 마이크 허용·거부, 녹음 중지, 인식문 수정,
   키보드 직후 제출, 음성 재생/중지, 공식 링크 이동을 확인한다.
3. 공식 자료의 접수 상태·링크·정보 확인일을 다시 검증한다.
4. 적은 데이터와 미확인 과금 단위·초보 자격 때문에 추천할 수 없는 경우를
   포트폴리오에서 명확히 설명한다. 실제 사용자 사용성 검증은 별도다.

## GitHub 반영 전 최종 점검 — 2026-11-09

### API 호환성: 문서·로컬 확인과 실호출 구분

| 대상 | 확인 근거 | 판정 |
| --- | --- | --- |
| `openai==3.46.0` | [OpenAI 공식 SDK 릴리스](https://github.com/openai/openai-python/releases/tag/v3.46.0), 설치된 배포 메타데이터와 메서드 서명 | 공식 릴리스·로컬 설치·사용 인자 확인. Python >=3.10 필요 |
| `gpt-5.4-mini-2026-03-17` | [모델 문서](https://developers.openai.com/api/docs/models/gpt-5.4-mini) | 해당 스냅샷, Responses·Structured Outputs·reasoning low 지원을 문서에서 확인 |
| Responses `text.format` | [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses), 설치 SDK, 로컬 JSON Schema 검사 | strict JSON Schema 요청 형식 확인. 서버 측 실제 스키마 수락은 미검증 |
| STT `gpt-transcribe` | [Transcriptions API](https://developers.openai.com/api/reference/resources/audio/subresources/transcriptions/methods/create), 설치 SDK | 모델 ID·파일·ISO 언어 지정·prompt·JSON 응답·text 필드 확인. 실제 한국어 인식은 미검증 |
| TTS `gpt-4o-mini-tts` | [Speech API](https://developers.openai.com/api/reference/resources/audio/subresources/speech/methods/create), 설치 SDK | coral·instructions·MP3·speed=0.9는 문서 범위. 모델 Deprecated/2027-01-06 종료 예정. 실제 합성은 미검증 |

Speech API의 입력 한도는 4,096자이며 앱은 4,000자로 제한한다. 모델별 토큰 한도도
별도로 적용될 수 있으므로 이 문자 검사만으로 모든 긴 입력의 성공을 보장하지 않는다.
SDK→로컬 모의 HTTP 검사는 실제 OpenAI 계정의 권한·과금·할당량·모델 동작을 증명하지 않는다.
이번 점검에서 필요한 공식 문서는 열람했지만, 실 API 키는 없고 실호출도 하지 않았다.

### Community Cloud 설정

[의존성 공식 안내](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)와
[Secrets 공식 안내](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)를 확인했다.

1. 기존 main 배포를 유지하려면 **검토용 앱을 별도로 만들고** 저장소
   `alstj0606/ieum-ai`, 브랜치 `data/gangseo-official-activities`, entrypoint `app.py`를 선택한다.
   PR 생성만으로 기존 main 배포가 이 브랜치 화면으로 바뀌지는 않는다.
2. Python **3.12**를 선택한다. 고정한 Streamlit의 설치 메타데이터는 >=3.11,
   OpenAI SDK는 >=3.10이다. 현재 검증은 Linux/Python 3.12 환경이다.
3. 루트 `requirements.txt`의 Streamlit/OpenAI SDK를 설치한다. 앱 실행에
   Playwright·Chromium·Node·ffmpeg·별도 OS 패키지는 필요하지 않다.
4. 앱 Settings/Advanced settings의 Secrets에 위 TOML을 넣는다.
   키를 넣지 않으면 공식 조건 검색·기본 키워드 검색·가상 체험을 사용할 수 있다.
5. 실제 배포에는 로컬 테스트용 `OPENAI_BASE_URL`을 설정하지 않는다.
   `OPENAI_LOG=debug` 같은 요청 상세 로그도 켜지 않는다. 키 설정 후 필요하면 앱을 재시작한다.
6. HTTPS 앱 주소를 브라우저에서 직접 열어 마이크 권한·인식문 수정·음성 재생을
   실기기에서 확인한다. Community Cloud 실제 빌드/실행은 이번에 수행하지 않았다.

### 저장·로그 점검

- Git 반영 후보 파일과 도달 가능한 기존 이력에서 OpenAI 키 형태·개인키·
  주민등록번호 형태를 검사했고 일치 항목은 없었다. 이 패턴 검사만으로 모든 개인정보를
  탐지할 수 있는 것은 아니다. 데이터의 기관 공개 연락처와 테스트용 가짜 키는 남아 있다.
- 앱·서비스 코드의 파일 쓰기·로깅 경로도 검토했다. 공식 JSON을 읽는 경로 외에
  사용자 대화·키·녹음을 디스크에 쓰거나 출력하는 앱 코드는 없다.
  테스트용 WAV는 메모리에서 생성한다. 테스트 출력은 저장소 밖 개발 작업 폴더에 둔다.
- `.env`, `.streamlit/secrets.toml`, 비공개 데이터, 로그에 이어 오디오 확장자·
  대체 Secrets 파일·개발 scratch 폴더도 `.gitignore`로 제외했다.
- 대화·조건·인식문과 재생 음성은 브라우저/Streamlit 서버의 세션 메모리에 남을 수 있다.
  외부 API로 보낸 데이터의 제공자 보존 정책이나 실제 배포 호스팅 로그까지
  ‘저장되지 않는다’고 보증한 것은 아니다.
- 자동 테스트와 브라우저 검사는 이전과 같은 모의/로컬 범위다. 실제 AI·음성
  인식 품질이나 Community Cloud 배포 성공으로 표현하지 않는다.
- GitHub 반영 전 재실행에서도 unittest 50개·Chromium 7개 흐름이 모두 통과했다.
  별도로 API 키 없는 실제 Streamlit 서버의 공식 활동 검색·출처 링크와
  `/_stcore/health` HTTP 200도 확인했다. `pip check`와 스키마 로컬 검사도 통과했다.

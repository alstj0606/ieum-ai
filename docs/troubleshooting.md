# 주요 장애 트러블슈팅

중요한 장애만 이 파일에 누적한다. 작은 수정의 보고서나 중복 문서는 만들지 않는다. 가설과 로컬 검증을 실제 배포의 근본 원인·해결 완료로 기록하지 않는다.

## 2026-11-10 — Cloud `advance_step` ImportError

**상태: 최소 수정 및 로컬 회귀 검증 완료 / 실제 Cloud 근본 원인·정상 실행은 조사 중**

### 발생 상황과 실제 오류

사용자 제공 정보: `https://ieum-ai-demo.streamlit.app`, `alstj0606/ieum-ai / main`, Python **3.14.10**, Streamlit **1.66.1**. 재부팅 후에도 `services/institution_dialogue.py:8`에서 다음 오류가 반복됐다.

```text
ImportError: cannot import name 'advance_step' from 'services.application_helper'
app.py → ui/seongsan_app.py → services/institution_dialogue.py → services/application_helper.py
```

전체 원문 traceback, 실행 중 파일/커밋 SHA와 새 프로세스의 모듈 상태는 아직 확인하지 못했다. 사용자가 제공한 ‘오전 10:03 한국시간’과 GitHub 병합 기록의 시간대를 추가 확인 중이다.

### 확인한 사실

- 조사 기준 main은 `315b60bee6288b54574f018f85a15748547e8fed`이다. `advance_step`은 `065fdc9`(PR #17)에서 추가됐으며 수정 전 main의 `services/application_helper.py:77`에 최상위 함수로 존재한다. PR #18·#19는 이 함수를 변경하지 않았다.
- 해당 시작 경로의 즉시 import 그래프에 순환이 없으며, 관련 모듈 두 가지 import 순서가 새 프로세스에서 정상이다. 대소문자만 다른 Python 파일 충돌도 없다. 로컬의 `services.__path__`·helper `__file__`은 해당 체크아웃이다. Cloud 모듈 경로의 실제 값은 미확인이다.
- 기존 성산 코드는 순수한 단계 계산 함수 하나 때문에 강서구 프로그램 도우미 전체를 import했다. 강서구 모듈의 export가 없는 상태를 통제 실험으로 만들면 같은 ImportError가 발생한다. 이것은 실패 조건/의존 관계를 입증하며 실제 Cloud가 그 상태였다는 증거는 아니다.
- GitHub API 기준 병합 시각(한국시간)은 PR #17 **18:05:41**, #18 **18:52:25**, #19 **19:03:25**다. 따라서 ‘10:03’ 로그가 UTC 표기인지, 한국시간인지, 이전 로그인지 원문 확인이 필요하다. 시각 차이만으로 배포 원인을 확정하지 않는다.
- 저장소의 직접 의존성은 `streamlit==1.66.1`, `openai==3.46.0`, `google-genai==3.0.0`이며 Python 고정 파일은 없다. 이 사실만으로 버전 오류라고 판단하지 않는다.

### 조사·시도·결과

| 시도 | 결과와 해석 |
|---|---|
| 기존 Linux/Python 3.12.14 및 별도 깨끗한 3.13.5 | 관련 import·186개 자동 테스트·실제 로컬 Streamlit 시작/화면 흐름 통과. Cloud 정상 증거 아님 |
| 오래된 helper를 메모리에 둔 통제 실험 | 현재 디스크에 함수가 있어도 같은 오류를 재현. 캐시가 원인이라고 확정하지 않음 |
| Cloud 재부팅 | 사용자 보고상 동일 오류 지속. 반복 재부팅을 최종 해결로 제시하지 않음 |
| 깨끗한 Python 3.14.9, 수정 전 main | 고정 의존성 설치와 186개 테스트 통과. Python 3.14 자체를 직접 원인으로 볼 근거 없음 |
| 정확한 Python 3.14.10, 수정 전 main 별도 사본 | 고정 의존성 설치·186개 테스트 및 실제 Streamlit/Chromium 시작·단계 이동·강서구 검색·상태 복귀 통과. 이 패치 버전만으로 오류 재현되지 않음 |
| 수정본: 3.12.14 / 3.14.9 / 3.14.10 | 각각 자동 테스트 191개 통과. 기존 helper export가 없거나 helper import가 차단돼도 성산 시작/단계 이동이 되는 새 회귀 검사 포함 |
| 수정본: Python 3.14.10 실제 Streamlit 서버 | Chromium 320/390/768px에서 첫 화면·회원 선택·다음/이전·강서구 검색·상태 복귀 통과 |

3.14.10은 uv 기본 다운로드 목록에 없었으나 CPython 공식 소스 태그와 Astral의 `python-build-standalone` 20261026 배포본을 확인해 실행 파일을 확보했다. 게시 SHA-256과 다운로드 파일의 일치도 확인했다. Cloud와 Python 버전은 같지만 OS 이미지·컴파일 옵션·모든 전이 의존성이 동일하다는 보장은 없다. 실제 API는 호출하지 않았다.

### 확인된 근본 원인과 최소 수정

**실제 Cloud에서 함수가 보이지 않았던 근본 원인은 아직 미확정이다.** 파일/커밋 혼재, 모듈 캐시·초기화 상태, 실제 배포 환경 차이를 구분할 원문 로그가 필요하다. 함수 누락·순환 import·대소문자 충돌·Python 3.14.10 자체 결함은 현재 재현되지 않았다.

확인된 불필요한 시작 의존 관계와 보고된 실패 import 경로를 다음과 같이 제거했다.

- `services/guide_navigation.py`: 기존 `advance_step` 구현을 변경 없이 이동한 무의존 순수 모듈.
- `services/institution_dialogue.py`: 새 모듈에서 직접 import하므로 성산 시작 시 `services.application_helper`를 로드하지 않는다.
- `services/application_helper.py`: 같은 함수를 re-export해 기존 강서구 API와 동작을 보존한다. 구현을 중복 추가하지 않는다.
- import 오류를 감추는 except/fallback, 강제 reload, sys.modules 조작은 실행 코드에 넣지 않았다. 모듈 상태를 바꾸는 실험은 회귀 테스트의 별도 프로세스에만 있다.

이는 검증된 **의존 분리 및 실패 경로 제거 조치**다. Cloud 장애의 최종 해결이라고 확정한 것은 아니다. README, PR #18 스타일, 공식 데이터, UI/세션 흐름, Gemini·음성 설정, requirements는 변경하지 않았다.

### 실제 Cloud 검증과 미확인 항목

앱 URL 직접 열람은 이 환경 프록시의 CONNECT 403으로 차단됐고 웹 열람 도구도 접근하지 못했다. 이는 Cloud 앱이 HTTP 403을 반환했다는 뜻이 아니다. 공유 브라우저도 요구 정보 로딩 오류로 페이지를 확인하지 못했다. 관리 로그에 접근할 수 없어 사용자의 요약 외 실제 배포 상태를 확인하지 못했다.

필요한 자료는 최초 Traceback부터 마지막 줄까지의 **전체 원문**(`partially initialized module` 여부 포함), checkout/pull/build의 커밋 SHA(표시 시), Python·Streamlit 설치/시작 행, 원문 로그 시각과 시간대다. GitHub main 파일과 Cloud가 실행한 파일을 구분해야 한다. 키·Secrets·사용자 정보는 수집하지 않는다.

Cloud에서는 PR 브랜치를 별도 시험 배포해 먼저 확인할 수 있다. 실제 시작 로그의 대상 커밋과 `app.py` 진입점을 확인하고 첫 화면·회원 선택·다음/이전·강서구 왕복을 검증해야 한다. 새 코드 반영 이후에도 오류가 옛 `from services.application_helper import advance_step` 줄을 가리킨다면 이전 로그/코드·프로세스 참조 여부를 조사할 단서다. 그 사실만으로 원인을 단정하지 않는다.

**최종 해결 방법/완료 판정: 조사 중. 실제 Cloud 정상 실행과 새 로그의 ImportError 부재 확인이 남아 있다.**

### 재발 방지

`tests/test_startup_navigation.py`에 무의존 import, 기존 API 동일 함수 호환, 단계 범위, legacy export가 없는 상태, legacy helper를 import할 수 없는 새 프로세스의 Streamlit ScriptRunner 시작·다음/이전·rerun 검사를 추가했다. 기존 회귀 186개는 유지한다. 실제 서버/브라우저 검사와 단순 import 검사를 구분하고, 재발 시 이 기록에 실제 배포 증거와 확정 원인만 이어 갱신한다.

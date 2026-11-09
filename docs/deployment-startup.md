# 배포 ImportError 점검 (2026-11-10)

## 확인한 사실

- 조사 기준 GitHub main은 `4db9ebf` (PR #10 병합)이다.
- `app.py`는 `choose_alternative`를 가져오며, 같은 커밋의 `services/dialogue.py` 183행에 최상위 함수로 실제 정의되어 있다.
- PR #10 이전 main `facc6e5`의 대화 모듈에는 이 함수가 없다.
- 현재 main을 새 Python 프로세스에서 검사하면 모든 app 서비스 import가 성공한다.
- 새 Streamlit 프로세스와 실제 Chromium 세션으로 첫 화면, 마이크 표시, 텍스트 제출, 걷기의 공식 대안 버튼까지 확인했다. 서버 health 응답만으로 앱 실행을 판정하지 않았다.
- 이전 버전 모듈을 `sys.modules`에 남긴 별도 프로세스에서는 디스크의 현재 파일에 함수가 있어도 동일한 이름의 ImportError가 재현됐다. 조사 과정에서 운영 파일은 수정하지 않았다.

## 아직 확인하지 못한 것

사용자가 제공한 로그는 모듈 경로와 import 이름만 보여준다. 실제 Community Cloud의 checkout 커밋, 디스크 파일 내용, 메모리에 적재된 모듈 버전, 배포 설정은 직접 확인하지 못했다. 따라서 ‘캐시가 원인’, ‘배포 버전 불일치’라고 확정할 수 없다.

가능성은 새 app.py와 이전 대화 모듈의 혼재, 업데이트 전 모듈을 유지한 실행 프로세스, 다른 브랜치/앱 설정이다. 로그에 경로가 `/mount/src/ieum-ai/services/dialogue.py`라고 나와도 그 파일의 커밋이나 현재 메모리 코드까지 증명하지는 않는다. 현재 main의 함수 자체가 누락되었다는 증거는 없다.

## Community Cloud에서 확인할 순서

1. 앱 관리 화면에서 저장소가 `alstj0606/ieum-ai`, 브랜치가 `main`, 실행 파일이 루트 `app.py`인지 확인한다. GitHub main에 PR #10이 포함돼 있는지 확인한다. 이번 테스트 PR을 먼저 병합해야 복구되는 구조는 아니다.
2. 앱 메뉴의 **Reboot app**으로 프로세스를 재시작한다. 브라우저 새로고침이나 Streamlit 데이터 캐시 비우기만으로 서버의 기존 Python 모듈이 교체됐다고 판단하지 않는다. Secrets나 데이터를 삭제할 필요는 없다.
3. 새 시작 로그와 실제 앱 첫 화면을 확인한다. 로그에 checkout 커밋 정보가 있다면 현재 main과 대조한다. 키/Secrets 전체나 원본 사용자 대화는 공개하지 않는다.
4. ‘강서구 걷기 프로그램 찾아줘’를 입력해 ‘파크골프 대안 보기’가 나타나는지 확인한다. 이후 대안 버튼, 보조 메뉴, 마이크 표시도 확인한다. 실제 STT/TTS와 Gemini 연결은 별도 API 검증이다.
5. 같은 오류가 계속되면 오류 발생 시각, 배포 branch/entrypoint, 로그에 나타난 커밋 정보(있는 경우), 민감정보를 뺀 traceback만 확인한다. 최신 코드 재동기화가 필요하면 동일 repo/main/app.py와 기존 Secrets 설정을 보존해 재배포한다. 먼저 기존 앱을 삭제하거나 키를 코드에 옮기지 않는다.

자동 import fallback이나 `choose_alternative`의 중복 정의를 추가하지 않았다. 버전 혼재를 숨기면서 대안 기능을 끄는 수정도 하지 않았다. 복구 후에도 문제가 재현되면 실제 배포 버전을 기준으로 추가 조사해야 한다.

## 추가된 회귀 검사

```bash
python -m unittest discover -s tests
# 별도 테스트 도구인 Playwright와 Chromium이 설치된 개발 환경에서 실행
PYTHON=python node tests/browser_startup.cjs
```

- `tests/test_startup.py`: app.py의 AST에서 `services.*` import 목록을 동적으로 읽고 **새 프로세스**에서 모든 이름의 존재, 로컬 저장소에서의 import, 호출되는 이름의 callable 여부를 검사한다. `choose_alternative`도 명시적으로 확인한다.
- 같은 파일의 새 프로세스 AppTest: 키 없는 설정에서 app.py 실행, 예외 없음, 이음 AI 제목·질문창·초기 상태를 검사한다.
- `tests/browser_startup.cjs`: 임시 포트에 새 Streamlit 서버를 실행하고 Chromium 세션을 열어 실제 앱 실행과 대안 추천까지 확인한다. 테스트 종료 시 서버와 브라우저를 정리한다. API 키/원본 런타임 로그를 출력하지 않는다.

자동 테스트 114개와 신규 실제 서버 브라우저 스모크 1개가 통과했다. 이 변경에서는 기존 19개 브라우저 흐름 전체를 재실행하지 않았다. 실제 배포 서버, Gemini/OpenAI 실호출, Safari/모바일 실기기는 검증하지 않았다.

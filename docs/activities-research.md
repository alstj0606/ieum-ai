# 서울 강서구 공식 활동 자료 — 2026-11-09 확인

기준 커밋: `c55f830` (main). 한국 날짜 2026-11-09에 공식 페이지 본문을
웹 열람 도구로 확인했다. 검색 결과 요약만으로 확정한 데이터는 없다.
각 페이지의 게시·기준 날짜와 이번 확인일은 다르다. 이 자료는 실시간
접수 조회 결과가 아니며, 기관에 전화하거나 현장에서 확인하지 않았다.

## 선정 자료와 확인 범위

| 활동 | 공식 출처 | 확인 내용 | 접수·운영 해석 및 미확인 사항 |
| --- | --- | --- | --- |
| 하반기 슬로우조깅(40세 이상) | [구 공공체육시설 모집 공고](https://sports.gangseo.seoul.kr/fmcs/30?action=read&action-value=449f756dd3fc684c50e1016d83c6e3df) | 강서구민 40세 이상, 마곡광장, 9~11월 월 18:30~19:30, 무료, 8/18 09:00~8/21 18:00 온라인 신청 후 추첨 | 모집 기간 종료. 현재 추가 모집·정확한 운영 시작/종료일·도로명주소는 미확인. 운영 예정 기간 안에 있다는 이유로 현재 참여 가능하다고 표시하지 않음. |
| 공항동문화체육센터 효도아쿠아 | [프로그램 안내](https://sport.gssi.or.kr/page/prgGuide/07/) / [시설·주소](https://sport.gssi.or.kr/page/sisul/07/) | 13:00~13:50, 월수금·화목별 및 60세 전후 요금 안내, 시설 주소 | 안내 자체가 **2025-08-05 기준**. 2026년 현재 운영·접수·단위요금은 미확인. 여러 요금 중 임의로 하나를 대표 요금으로 선택하지 않아 `fee_amount=null`; 알려진 요금들은 `fee_notes`에 보존. 어르신 전용으로 단정하지 않음. |
| 똘레랑스 인문학 강좌 | [허준박물관 교육 상세](https://culture.gangseo.seoul.kr/gsfc/education/view.do?eduSn=173&menuNo=800077) | 성인, 시청각실, 9/16~11/11, 무료, 접수표 마감, 시설 주소 | 상단 접수 종료일 9/14와 상세 표 9/13 18:00이 상충해 종료값은 null. 첫 일정만 10~12시로 표시되어 전체 강좌의 시간대로 일반화하지 않음. 세부 시간표 이미지·신청 절차는 미확인. |
| 동의보감 뷰티시크릿 5회차 | [허준박물관 교육 상세](https://culture.gangseo.seoul.kr/gsfc/education/view.do?eduSn=178&menuNo=800077) | 모든 성인, 체험교육실·전시실, 11/21 10:20~12:00, 1인 1회 10,000원, 접수표 9/30 10:00~11/20 17:00 | 접수표 **15/15, 마감**. 날짜가 남아도 접수 가능으로 추정하지 않음. 온라인 신청 세부 단계는 미확인. |
| 제27회 강서국악한마당 | [강서아트리움 행사 상세](https://culture.gangseo.seoul.kr/gsfc/culture/gsculture/event/view.do?cultureSn=268&menuNo=800169) | 11/14 15:30, 아리홀, 전석 무료, 예매 없이 현장 선착순, 시설 주소 | 사전 모집이 아닌 예정 행사. 연령 제한·종료 시각·좌석 확보는 미확인. `walk_in`은 현재 입장 가능을 의미하지 않음. |

주소는 시설 소개 또는 상세 페이지 하단의 해당 시설 주소만 사용했다.
분류·활동 종류·태그는 확인한 활동 내용에 붙인 검색용 편집 값이다.
이를 공식 참여 자격이나 건강상 적합성의 근거로 사용하지 않는다.
이번 선정에는 독립적인 사회참여 활동은 포함하지 못했다.

## 접근 실패·선정 제외

| 확인한 URL | 결과 | 처리 |
| --- | --- | --- |
| https://www.gangseo.seoul.kr/edu/edu050134 | 502 Bad Gateway (재확인 시에도 실패) | 평생학습 공지에서 개별 강좌를 확정하지 않음 |
| https://www.gangseo.seoul.kr/reserve | 502 Bad Gateway | 통합예약 접수 상태 확인 불가 |
| https://jachi.gangseo.seoul.kr/main | 시간 초과 | 자치회관 프로그램 미수록 |
| https://www.gangseosenior.or.kr/ | 시간 초과, 재확인 502 | 복지관 프로그램 미수록 |
| https://sport.gssi.or.kr/ | 최초 시간 초과 | 하위 시설·프로그램 안내 URL은 이후 열람 성공 |
| https://sport.gssi.or.kr/lecture/list/01 | 시간 초과 | 실제 수강신청 상태·절차 미확인 |

오류는 이번 열람 도구에서 관찰한 결과이며 사이트 전체의 장애라고
확정하지 않는다. 다른 지역·비공식 블로그의 내용을 대체 근거로 쓰지 않았다.

## 데이터 계약

- 최상위 JSON은 활동 객체 목록이다. 최소 항목 외에 `registration_status`,
  `status_notes`, `fee_notes`, `verification_notes`를 두어 근거와 한계를 보존한다.
- `schedule`: `text`, `starts_on`, `ends_on`, `time_slots`, `notes`.
  날짜가 월 단위로만 나오면 정확한 날짜는 null이다.
- `registration_period`: null 또는 `starts_at`, `ends_at`, `notes` 객체.
  일시는 시간대가 포함된 ISO 형식. 상충하는 종료일은 null로 보존한다.
- `fee_amount`: 원화 정수. 무료는 0, 단일 금액을 확정할 수 없으면 null.
  `fee_unit`이 null이면 월 요금 등으로 임의 해석하지 않는다.
- `registration_status`: `closed`(페이지 마감 또는 공고 기간 종료),
  `unknown`(접수 미확인), `walk_in`(사전 예매 없는 현장 입장),
  `open`(공식 접수 중 표시 확인). 확장 조사 후 open 자료는 4건이다.
- `official_url`은 공식 안내·참여 정보를 확인할 페이지이며, 반드시 신청
  폼이라는 뜻은 아니다. `source_url`은 실제 확인한 근거 페이지다.
- 모든 수록 자료는 `is_demo=false`. 기존 `demo_program.json`은 별도 유지한다.

## 검색 사용법

```python
from datetime import date
from services.activities import load_activities, search_activities

activities = load_activities()
result = search_activities(
    activities,
    region="강서구",
    activity_type="국악공연",
    time_slot="오후",
    tags=["국악"],
    as_of=date(2026, 11, 9),
)
# result["activities"]: 최대 3건 / result["message"]: 결과·결과 없음 안내

# 마감·과거·접수 미확인 자료를 살펴보는 조사 목적 검색
archived = search_activities(activities, include_unavailable=True)
```

- 조건 간 AND, 여러 관심 태그도 모두 일치해야 한다. 활동 종류·태그는
  정확 일치, 지역은 문자열 부분 일치다. 자연어 이해·동의어 확장은 없다.
- 오전/오후/저녁은 각각 시작 시각 00~12시 미만/12~18시 미만/18~24시
  기준으로 확인한 시간에만 부여한다. 전체 회차 시간 미확인은 빈 목록이다.
- 기본 검색은 마감·미확인·시연·종료일 미확인·이미 종료한 활동을 제외한다.
  확인일 이후 바뀐 실제 운영·접수 가능성을 보증하지 않는다.
- `as_of`에 date를 주면 한국 날짜 단위로 비교한다. 당일 마감 시각을
  판단하려면 시간대 포함 datetime을 준다. 미지정 시 한국 현재 시각을 사용한다.
- 조건에 안 맞으면 빈 목록과 안내를 반환한다. 태그·지역·시간을 임의로
  완화하거나 누락 값을 채우지 않는다. 원본 순서로 최대 3건이며 추천 순위가 아니다.
- 이 문서의 조사·검색 단계 이후 공식 검색을 앱에 연결했다. 현재 대화·화면·음성
  동작과 검증 한계는 [AI·음성 구현 안내](ai-voice.md)를 참고한다. 이 조사 기록의
  공식 출처·확인일은 변경하지 않았다.

## 검증 방법

저장소 루트에서 `python -m unittest discover -s tests -v`.
표준 라이브러리 unittest와 기존 Streamlit AppTest만 사용하며 추가 패키지는 없다.
테스트는 데이터 형식·검색·누락 값·마감 필터·기존 시연 흐름을 검사한다.
자동 테스트 통과는 원격 페이지의 실시간 접수 상태 검증을 대신하지 않는다.

## 2차 확장 조사 — 2026-11-09

기존 5건을 유지하고 아래 5건을 추가했다. 기준일의 상태는 총 10건 중
접수중 표시 4건, 향후 현장 선착순 행사 1건, 마감 4건, 미확인 1건이다.
기본 검색 후보는 5건이며 응답에는 최대 3건만 반환한다. 이 숫자는
잔여석 확인·이용 확정 또는 누구나 당일 참여 가능하다는 의미가 아니다.

### 추가 자료와 공식 출처

| 활동 | 확인한 공식 출처 | 확인 내용 | 상태와 한계 |
| --- | --- | --- | --- |
| 11/21 대시민 정비사업 아카데미(강서구) | [공공서비스예약 상세](https://yeyak.seoul.go.kr/web/reservation/selectReservView.do?rsv_svc_id=S261001182724664008) | 서울시민 누구나, 곰달래문화복지센터 7층 강당, 11/21 14~16시, 무료, 선착순 130명, 인터넷·현장/방문 신청. 접수 10/1 00:00~11/20 10:00 | 접수중(Open) 표시. 잔여석·방문 접수 장소는 미확인. 전화는 문의처이며 전화 신청으로 기록하지 않음. 여가 체험이 아닌 시민교육으로 분류. |
| 서남센터 파크골프장(18홀) | [공공서비스예약 상세](https://yeyak.seoul.go.kr/web/reservation/selectReservView.do?locale=ko&rsv_svc_id=S230131090246367142) / [서울물재생시설공단 안내](https://swr.or.kr/cpage/citizen/seonam_athletic/guidance.do?menu_cd=C0020) | 인터넷 선착순 예약, 기본료 3,000원. 이용일 10일 전 06시~전날까지 예약, 월요일 휴장, 매년 4~12월 개장. 일반인·장애인별 회차 구분 | 접수중 표시. **11/9는 월요일 휴장**이므로 향후 예약 후보로만 안내. 빈자리 미확인. 두 공식 페이지의 종료시간(17/18시)·홀수(18/9홀)가 상충해 메모 보존. 강습이 아닌 시설 이용이며 초보 교육 이수 유의사항 유지. |
| 개화산 치유센터 여백의 숲(11월) | [공공서비스예약 상세](https://yeyak.seoul.go.kr/web/reservation/selectReservView.do?rsv_svc_id=S261023180539894019) | 여성, 무료, 오전 10~12시, 선착순 10명, 인터넷 신청. 서비스 기간 10/25~11/25, 접수 10/25 09시~11/23 18시 | 접수중(Open) 표시. 개별 운영일·잔여석은 미확인. 본문/지도 주소가 상충해 address=null, 기관에 집결지 확인 필요. 무료라는 이유로 전화·현장 신청 가능으로 확대하지 않음. |
| 나만의 미니정원_한컵의 숲(11월 성인) | [공공서비스예약 상세](https://yeyak.seoul.go.kr/web/reservation/selectReservView.do?reSvc=Y&rsv_svc_id=S261024154354557455) / [서울식물원 11월 공지](https://botanicpark.seoul.go.kr/front/board/newsView.do?pageIndex=1&searchCondition=&searchKeyword=&sn=20762) | 성인, 숲문화학교, 11/19·26 10~11:30, 인당 10,000원. 인터넷 선착순 8명, 접수 10/25 10시~11/24 17시 | 접수중(Open) 표시. 예약 서비스 전체 기간(10/24~11/30)과 실제 회차 날짜를 분리. 회차별 좌석 미확인, 5명 미만 시 취소 가능. 입장료 포함 여부 미확인. |
| 서울식물원 11월 전시온실 야간개장 | [공공서비스예약 상세](https://yeyak.seoul.go.kr/web/reservation/selectReservView.do?rsv_svc_id=S261102100634309493) / [서울식물원 공지](https://botanicpark.seoul.go.kr/front/board/newsView.do?pageIndex=1&searchCondition=&searchKeyword=&sn=20821) | 11/13·14·27·28 18:30~20:30, 1인 5,000원. 인터넷만 가능, 전화·현장 추가 입장 불가, 예약 후 2시간 내 결제 | **예약마감(Reservation deadline)** 표시. 미래 행사·접수기간 잔여를 이유로 추천 후보에 넣지 않음. 취소표 가능성도 추정하지 않음. |

영문으로 렌더링된 일부 예약 페이지의 `Open`/`Reservation deadline`은
각각 접수중/예약마감 표시로 기록했다. 페이지 표시를 열람한 것이며 로그인 후
실제 회차 선택·신청·결제는 하지 않았다. 공공서비스예약 목록은 갱신 시차가
있을 수 있어, 목록 검색 요약 대신 개별 상세 페이지를 근거로 사용했다.

### 추가 접근·검증 한계

- [서울 열린데이터광장 강서구 문화행사 데이터셋](https://data.seoul.go.kr/dataList/OA-12171/S/1/datasetView.do)을
  후보 탐색에 활용했다. 본문에 연계 시차 안내가 있어 접수 상태는 개별 상세와 대조했다.
- 여백의 숲 상세 URL에 `locale=ko`를 넣었을 때 도구 접근 실패. 같은 서비스 ID의
  기본 URL은 열람 성공했으며 그 본문만 근거로 기록했다.
- [정원 소리: 소금 힐링 연주 예약 상세](https://yeyak.seoul.go.kr/web/reservation/selectReservView.do?reSvc=N&rsv_svc_id=S261020112156217559)는
  대기/차단 화면만 반환했다. 식물원 11월 공지에 활동 정보는 있으나
  접수 상태를 추가 확인하지 못해 이번 활동 목록에 넣지 않았다. 차단은 우회하지 않았다.
- 정원지원실 ‘이끼 수집가의 방’ 공지는 본문이 이미지 위주여서 세부 일정·신청
  조건을 확정하지 않고 선정에서 제외했다.
- 현재 추가 목록에는 전화 신청을 검증한 프로그램이 없다. 문의 전화와 전화 접수는 구분한다.
- 대상 자격은 원문대로 유지했다. 성인 프로그램이나 여성 대상 프로그램을
  ‘어르신 누구나 가능’으로 바꾸지 않았다.

### 검색 보강

- 저장된 `registration_status`는 확인 당시 상태로 보존한다.
  검색 결과의 `availability_status`는 기준 시점에 따라 `open`, `walk_in`,
  `closed`, `unknown`, `upcoming`(접수 시작 전), `ended`(활동 종료)로 계산한다.
- 확인일 이전 시점의 모집 상태를 현재 자료로 소급 추정하지 않고 unknown으로 둔다.
- `statuses=["open"]`은 접수중 후보만, `statuses=["walk_in"]`은 현장 참여 안내만
  반환한다. 이 인자는 기본 상태 필터를 대체하므로 `statuses=["closed"]`로
  마감 자료를 조사할 수도 있다. `category="체육"` 등 분류 검색도 지원한다.
- 기본 조회는 open/walk_in만 포함한다. 실제 운영일·휴장·자격·일별 예약 창은
  `schedule`, `registration_method`, `status_notes`를 함께 읽어야 한다.
  회차별 빈자리나 특정 날짜 예약 가능 여부를 자동 판정하는 기능은 없다.
- `open`이어도 접수 기간 또는 활동 종료일을 확정할 수 없으면 기본 후보에서
  제외한다. 현재 새 open 자료 4건은 접수기간과 서비스/활동 종료일을 확인했다.
- 날짜별로 개방되는 파크골프장도 총 접수기간만으로 모든 날짜·시간을
  예약 가능하다고 판단하지 않는다. 개별 예약 규칙은 원문 메모로 보존한다.
- 반환 구조에 `total_matches`(3건 제한 전 조건 일치 수)를 추가했다.
  `summarize_activities(as_of=...)`는 전체 공식 자료의 상태별 수를 집계한다.
- Python date 입력은 하루 단위 비교로 유지한다. 기본값은 한국 현재 시각,
  시간대 있는 datetime 입력은 접수 시작·종료 시각까지 비교한다.

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from services.activities import search_activities, summarize_activities

reference = datetime(2026, 11, 9, 10, 0, tzinfo=ZoneInfo("Asia/Seoul"))
summary = summarize_activities(as_of=reference)
# total=10, open=4, walk_in=1, closed=4, unknown=1
result = search_activities(statuses=["open"], as_of=reference)
# total_matches=4, activities는 최대 3건
```

기존 15개 테스트 항목을 유지하고 확장 자료에 맞게 상태 건수·종료 행사
검색 조건을 갱신했다. 신규 접수중 활동 검색, 분류·상태별 필터, 전체 집계,
당일 마감 시각과 UTC 변환, 확인일 이전 추정 금지 등을 추가 검증한다.

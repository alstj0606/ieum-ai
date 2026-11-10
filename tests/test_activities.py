"""네트워크 없이 공식 자료의 저장 계약·검색·기존 앱을 검증한다."""

from copy import deepcopy
from datetime import date, datetime
import json
from pathlib import Path
import tempfile
import unittest

from services.activities import (
    availability_status, load_activities, search_activities, summarize_activities,
    validate_activities,
)


ROOT = Path(__file__).resolve().parents[1]
CHECK_DATE = date(2026, 11, 9)


class ActivitiesTest(unittest.TestCase):
    def setUp(self):
        self.data = load_activities()

    def search(self, **kwargs):
        return search_activities(self.data, as_of=CHECK_DATE, **kwargs)["activities"]

    def test_official_data_contract(self):
        self.assertEqual(len({row["id"] for row in self.data}), len(self.data))
        self.assertTrue(self.data)
        self.assertTrue(all(row["is_demo"] is False for row in self.data))
        self.assertTrue(all(row["verified_at"] == "2026-11-09" for row in self.data))
        self.assertEqual({row["category"] for row in self.data}, {"체육", "문화·취미", "평생학습"})

    def test_loader_validates_external_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "activities.json"
            path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(load_activities(path), self.data)
            path.write_text('{"id": "not-a-list"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_activities(path)
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                load_activities(path)

    def test_rejects_missing_wrong_types_and_invalid_dates(self):
        mutations = [
            lambda row: row.pop("target"),
            lambda row: row.update(fee_amount=False),
            lambda row: row.update(fee_amount=-1),
            lambda row: row.update(fee_amount="0"),
            lambda row: row.update(is_demo="false"),
            lambda row: row.update(tags="운동"),
            lambda row: row.update(verified_at="2026-02-30"),
            lambda row: row.update(source_url="javascript:alert(1)"),
            lambda row: row.update(registration_status=[]),
            lambda row: row["schedule"].update(time_slots=["미확인"]),
            lambda row: row["schedule"].update(starts_on="2027-01-01", ends_on="2026-12-31"),
            lambda row: row["registration_period"].update(ends_at="2026-08-21T18:00:00"),
            lambda row: row["registration_period"].update(ends_at="2020-08-21T18:00:00+09:00"),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                row = deepcopy(self.data[0])
                mutate(row)
                with self.assertRaises(ValueError):
                    validate_activities([row])
        with self.assertRaises(ValueError):
            validate_activities([self.data[0], self.data[0]])

    def test_search_each_activity_type_including_archived(self):
        for row in self.data:
            with self.subTest(activity_type=row["activity_type"]):
                found = self.search(activity_type=row["activity_type"], include_unavailable=True)
                self.assertIn(row["id"], [item["id"] for item in found])

    def test_combined_region_time_and_all_tags(self):
        found = self.search(activity_type="국악공연",
                            region="강서구", time_slot="오후", tags=["국악", "공연"])
        self.assertEqual([row["id"] for row in found], ["gangseo-gugak-20261114"])
        self.assertEqual(self.search(tags=["국악", "수중운동"], include_unavailable=True), [])

    def test_no_match_does_not_relax_conditions(self):
        for query in ({"region": "부산"}, {"activity_type": "수영"},
                      {"time_slot": "저녁"}, {"tags": ["존재하지않는태그"]}):
            result = search_activities(self.data, as_of=CHECK_DATE, **query)
            self.assertEqual(result["activities"], [])
            self.assertIn("활동이 없어요", result["message"])

    def test_unknown_schedule_not_assumed_to_be_morning(self):
        found = self.search(activity_type="인문학", time_slot="오전", include_unavailable=True)
        self.assertEqual(found, [])

    def test_zero_and_null_preserved_without_mutation(self):
        original = deepcopy(self.data)
        free = self.search(activity_type="국악공연")[0]
        unknown = self.search(activity_type="아쿠아로빅", include_unavailable=True)[0]
        self.assertEqual(free["fee_amount"], 0)
        self.assertIsNone(unknown["fee_amount"])
        self.assertIsNone(unknown["registration_period"])
        unknown["tags"].append("사용자 수정")
        self.assertEqual(self.data, original)

    def test_maximum_three_and_smaller_limit(self):
        self.assertEqual(len(self.search(include_unavailable=True, limit=99)), 3)
        self.assertEqual(len(self.search(include_unavailable=True, limit=1)), 1)

    def test_closed_full_and_unknown_excluded_by_default(self):
        result = search_activities(self.data, as_of=CHECK_DATE)
        self.assertEqual(result["total_matches"], 5)
        self.assertTrue(all(row["availability_status"] in {"open", "walk_in"}
                            for row in result["activities"]))
        # 접수 종료일이 미래여도 페이지가 마감이면 결과에 넣지 않는다.
        self.assertEqual(self.search(activity_type="전시연계체험"), [])
        self.assertEqual(self.search(activity_type="아쿠아로빅"), [])

    def test_past_event_excluded_and_archive_message(self):
        result = search_activities(self.data, activity_type="국악공연", as_of=date(2026, 11, 15))
        self.assertEqual(result["activities"], [])
        archived = search_activities(self.data, as_of=CHECK_DATE, include_unavailable=True)
        self.assertIn("조사용", archived["message"])

    def test_demo_never_included_in_official_search(self):
        rows = deepcopy(self.data)
        for row in rows:
            row["is_demo"] = True
        self.assertEqual(search_activities(rows, include_unavailable=True)["activities"], [])

    def test_open_period_and_unknown_end_are_conservative(self):
        row = deepcopy(self.data[-1])
        row["registration_status"] = "open"
        row["registration_period"] = {
            "starts_at": "2026-11-01T10:00:00+09:00",
            "ends_at": "2026-11-10T18:00:00+09:00", "notes": None,
        }
        self.assertEqual(len(search_activities([row], as_of=CHECK_DATE)["activities"]), 1)
        self.assertEqual(search_activities([row], as_of=date(2026, 11, 11))["activities"], [])
        row["schedule"]["ends_on"] = None
        self.assertEqual(search_activities([row], as_of=CHECK_DATE)["activities"], [])

    def test_full_dataset_counts_before_result_limit(self):
        counts = summarize_activities(self.data, as_of=CHECK_DATE)
        self.assertEqual(counts, {
            "total": 10, "open": 4, "walk_in": 1, "closed": 4,
            "unknown": 1, "ended": 0, "upcoming": 0, "participation_options": 5,
        })
        result = search_activities(self.data, as_of=CHECK_DATE)
        self.assertEqual(len(result["activities"]), 3)
        self.assertEqual(result["total_matches"], 5)

    def test_each_new_open_activity_found_without_archive_flag(self):
        for kind in ("시민교육", "파크골프", "숲체험", "가드닝"):
            with self.subTest(kind=kind):
                rows = self.search(activity_type=kind)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["availability_status"], "open")

    def test_category_filter_and_explicit_status_filters(self):
        rows = self.search(category="체육")
        self.assertEqual([row["activity_type"] for row in rows], ["파크골프"])
        rows = self.search(statuses=["walk_in"])
        self.assertEqual([row["id"] for row in rows], ["gangseo-gugak-20261114"])
        result = search_activities(self.data, as_of=CHECK_DATE, statuses=["closed"])
        self.assertEqual(result["total_matches"], 4)
        self.assertIn("조사용", result["message"])
        rows = self.search(statuses=["unknown"])
        self.assertEqual([row["activity_type"] for row in rows], ["아쿠아로빅"])

    def test_closed_night_event_not_assumed_available_in_future(self):
        rows = self.search(activity_type="야간관람")
        self.assertEqual(rows, [])
        archived = self.search(activity_type="야간관람", include_unavailable=True)
        self.assertEqual(archived[0]["availability_status"], "closed")

    def test_exact_deadline_uses_time_and_timezone(self):
        row = next(row for row in self.data if row["activity_type"] == "시민교육")
        before = datetime.fromisoformat("2026-11-20T09:59:59+09:00")
        after = datetime.fromisoformat("2026-11-20T10:00:01+09:00")
        self.assertEqual(availability_status(row, as_of=before), "open")
        self.assertEqual(availability_status(row, as_of=after), "closed")
        same_after_utc = datetime.fromisoformat("2026-11-20T01:00:01+00:00")
        self.assertEqual(availability_status(row, as_of=same_after_utc), "closed")

    def test_before_verification_does_not_infer_old_open_status(self):
        row = next(row for row in self.data if row["activity_type"] == "가드닝")
        self.assertEqual(availability_status(row, as_of=date(2026, 11, 8)), "unknown")

    def test_future_opening_expired_period_and_ended_activity(self):
        row = deepcopy(next(row for row in self.data if row["activity_type"] == "시민교육"))
        row["registration_period"]["starts_at"] = "2026-11-10T10:00:00+09:00"
        self.assertEqual(availability_status(row, as_of=CHECK_DATE), "upcoming")
        self.assertEqual(search_activities([row], as_of=CHECK_DATE)["activities"], [])
        self.assertEqual(availability_status(row, as_of=date(2026, 11, 22)), "ended")
        counts = summarize_activities(self.data, as_of=date(2027, 1, 1))
        self.assertEqual(counts["participation_options"], 0)

    def test_missing_registration_period_remains_unknown(self):
        row = deepcopy(next(row for row in self.data if row["activity_type"] == "시민교육"))
        row["registration_period"] = None
        self.assertEqual(availability_status(row, as_of=CHECK_DATE), "unknown")

    def test_invalid_statuses_and_naive_datetime_rejected(self):
        for kwargs in ({"statuses": []}, {"statuses": "open"}, {"statuses": ["대기"]},
                       {"as_of": datetime(2026, 11, 9)}, {"category": " "}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                search_activities(self.data, **kwargs)

    def test_invalid_filters_raise_instead_of_ignoring(self):
        for args in ({"time_slot": "새벽"}, {"limit": 0}, {"limit": True},
                     {"tags": "국악"}, {"region": " "}, {"as_of": "2026-11-09"}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                search_activities(self.data, **args)


class ExistingAppTest(unittest.TestCase):
    def test_existing_demo_flow(self):
        from streamlit.testing.v1 import AppTest

        program = json.loads((ROOT / "data/demo_program.json").read_text(encoding="utf-8"))
        app = AppTest.from_file(str(ROOT / "gangseo_app.py")).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "이음 AI")
        app.chat_input(key="chat").set_value("   ").run()
        self.assertTrue(any(item.value == "질문을 먼저 적어주세요" for item in app.warning))
        app.button(key="demo_example").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any(item.value == program["name"] for item in app.subheader))
        for key in ("audience", "schedule", "fee", "registration_period"):
            self.assertTrue(any(program[key] in item.value for item in app.markdown))
        self.assertEqual(app.session_state["dialog"]["results"], [])
        app.button(key="reset").click().run()
        self.assertFalse(any(item.value == program["name"] for item in app.subheader))



if __name__ == "__main__":
    unittest.main()

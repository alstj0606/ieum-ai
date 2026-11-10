"""Official facts formatted for mobile; no API calls or new production data."""
from copy import deepcopy
from pathlib import Path
from datetime import date, datetime
from unittest import TestCase
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from services.activities import load_activities
from services.config import Settings
from services.recommendations import activity_facts, registration_display

DAY=date(2026,11,10)

class ReadableDetailsTest(TestCase):
    def setUp(self):self.rows=load_activities()

    def test_past_recruitment_compact_and_never_extrapolated(self):
        row=self.rows[0]
        dates,times,next_date=registration_display(row,as_of=DAY)
        self.assertEqual(dates,'2026.08.18 ~ 08.21')
        self.assertIn('09:00',times)
        self.assertEqual(next_date,'다음 접수 일정 미정')
        self.assertEqual(dict(activity_facts(row,as_of=DAY))['접수 상태'],'접수 마감')

    def test_future_intake_has_only_official_start_date_and_closed_conflict_is_safe(self):
        row=deepcopy(next(x for x in self.rows if x['activity_type']=='시민교육'))
        row['registration_period']={'starts_at':'2026-11-12T09:00:00+09:00','ends_at':'2026-11-13T18:00:00+09:00','notes':None}
        self.assertEqual(registration_display(row,as_of=DAY)[2],'2026.11.12')
        self.assertEqual(dict(activity_facts(row,as_of=DAY))['접수 상태'],'접수 시작 전')
        row['registration_status']='closed'
        self.assertEqual(registration_display(row,as_of=DAY)[2],'다음 접수 일정 미정')
        self.assertEqual(dict(activity_facts(row,as_of=DAY))['접수 상태'],'접수 마감')
        row['registration_status']='unknown'
        self.assertEqual(registration_display(row,as_of=DAY)[2],'다음 접수 일정 미정')

    def test_unknown_and_free_fields_and_no_future_prediction(self):
        row=next(x for x in self.rows if x['activity_type']=='아쿠아로빅')
        facts=dict(activity_facts(row,as_of=DAY))
        self.assertEqual(facts['비용'],'공식 자료 확인 필요')
        self.assertEqual(facts['접수 기간'],'공식 자료 확인 필요')
        self.assertEqual(facts['준비물'],'공식 자료 확인 필요')
        self.assertEqual(facts['다음 접수 예정일'],'다음 접수 일정 미정')
        facts=dict(activity_facts(self.rows[0],as_of=DAY))
        self.assertIn('무료',facts['비용'])
        self.assertEqual(facts['주소'],'공식 자료 확인 필요')
        forest=next(x for x in self.rows if x['activity_type']=='숲체험')
        self.assertEqual(dict(activity_facts(forest,as_of=DAY))['준비물'],'긴팔·긴바지·운동화·마실 물')

    def test_local_time_conversion_and_cross_year_period(self):
        row=deepcopy(self.rows[0])
        row['registration_period'].update(starts_at='2026-12-31T15:00:00+00:00',ends_at='2027-01-02T00:00:00+09:00')
        self.assertEqual(registration_display(row,as_of=DAY)[0],'2027.01.01 ~ 01.02')
        row['registration_period']['starts_at']='2026-12-31T09:00:00+09:00'
        self.assertEqual(registration_display(row,as_of=DAY)[0],'2026.12.31 ~ 2027.01.02')

    def test_open_state_expires_by_time_and_does_not_guess_next_date(self):
        row=next(x for x in self.rows if x['activity_type']=='시민교육')
        before=datetime.fromisoformat('2026-11-10T12:00:00+09:00')
        self.assertIn('접수중',dict(activity_facts(row,as_of=before))['접수 상태'])
        after=datetime.fromisoformat(row['registration_period']['ends_at'])
        from datetime import timedelta
        self.assertEqual(dict(activity_facts(row,as_of=after+timedelta(seconds=1)))['접수 상태'],'접수 마감')
        self.assertEqual(registration_display(row,as_of=after+timedelta(seconds=1))[2],'다음 접수 일정 미정')

    def test_choice_renders_one_card_before_explanations_and_keeps_history(self):
        with patch('services.config.load_settings',return_value=Settings()):
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run()
            app.chat_input(key='chat').set_value('강서구 걷기 프로그램 찾아줘').run()
            old_turns=len(app.session_state['turns'])
            button=app.button(key='alternative_슬로우조깅')
            self.assertEqual(button.label,'슬로우조깅 정보 보기 →')
            button.click().run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.session_state['turns']),old_turns+1)
            self.assertTrue(app.session_state['turns'][-1]['detail_first'])
            last=app.chat_message[-1]
            self.assertEqual(len(last.subheader),1)
            text='\n'.join(x.value for x in last.markdown)
            self.assertIn('2026.08.18',text)
            self.assertIn('다음 접수 일정 미정',text)
            self.assertNotIn('같은 지역의 대안 · 공식 자료 있음',text)
            self.assertNotIn('일반 활동 제안 · 실제 모집 프로그램 아님',text)
            self.assertNotIn('찾지 못했어요',text)
            self.assertEqual(len([b for b in last.button if b.key.startswith('alternative_')]),0)
            app.run()
            self.assertEqual(len(app.chat_message[-1].subheader),1)
            self.assertEqual(len(app.session_state['turns']),old_turns+1)

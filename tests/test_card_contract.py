"""Production records and deliberate legacy/malformed presentation fixtures; no API."""
from copy import deepcopy
from datetime import date
from pathlib import Path
import re
from unittest import TestCase
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from services.activities import load_activities
from services.card_view import CARD_FIELDS, REQUIRED_KEYS, card_facts
from services.date_display import registration_display, UNKNOWN, NEXT_UNKNOWN
from services.recommendations import activity_facts
from services.dialogue import new_state, handle_turn
from services.config import Settings
from services.alternative_paths import alternative_rank, related_options

ROOT=Path(__file__).resolve().parents[1]
DAY=date(2026,11,10)
ISO=re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}')

class CardContractTest(TestCase):
    def setUp(self):self.rows=load_activities()

    def test_all_ten_producers_satisfy_shared_contract_and_dates_are_formatted(self):
        self.assertEqual(len(self.rows),10)
        for row in self.rows:
            with self.subTest(record=row['id']):
                raw=dict(activity_facts(row,as_of=DAY))
                self.assertFalse(set(REQUIRED_KEYS)-raw.keys())
                facts=card_facts(row,as_of=DAY)
                self.assertTrue(all(isinstance(facts[key],str) and facts[key] for key in REQUIRED_KEYS))
                self.assertFalse(re.search(r'\d{4}-\d{2}-\d{2}', ' '.join(facts.values())))
                self.assertEqual(facts['다음 접수 예정일'],NEXT_UNKNOWN)

    def test_legacy_producer_missing_keys_is_diagnosed_and_raw_iso_reformatted(self):
        legacy=dict(activity_facts(self.rows[0],as_of=DAY))
        legacy.pop('준비물');legacy.pop('다음 접수 예정일')
        legacy['접수 기간']='2026-08-18T09:00:00+09:00 ~ 2026-08-21T18:00:00+09:00'
        with patch('services.card_view.activity_facts',return_value=list(legacy.items())),self.assertLogs('services.card_view',level='WARNING') as logged:
            facts=card_facts(self.rows[0],as_of=DAY)
        self.assertEqual(facts['접수 기간'],'2026.08.18 ~ 08.21')
        self.assertEqual(facts['준비물'],UNKNOWN)
        self.assertEqual(facts['다음 접수 예정일'],NEXT_UNKNOWN)
        self.assertIn('다음 접수 예정일',' '.join(logged.output))
        self.assertNotIn(self.rows[0]['name'],' '.join(logged.output))
        self.assertNotIn('2026-08-18T',' '.join(logged.output))

    def test_missing_and_none_source_fields_produce_safe_strings_not_free(self):
        row=deepcopy(self.rows[0])
        for key in ('fee_amount','address','schedule','registration_period','verification_notes','target','registration_method'):
            row[key]=None
        for key in ('facility_name','region','verified_at','status_notes'):
            row.pop(key)
        facts=card_facts(row,as_of=DAY)
        for key in ('비용','주소','일정','대상','장소','접수 기간','준비물'):
            self.assertEqual(facts[key],UNKNOWN)
        self.assertEqual(facts['접수 상태'],'접수 여부 확인 필요')
        self.assertNotIn('무료',facts['비용'])

    def test_invalid_naive_reversed_dates_never_leak_or_predict(self):
        for start,stop in [('bad','bad'),('2026-08-18T09:00:00','bad'),('2026-12-02T09:00:00+09:00','2026-12-01T09:00:00+09:00')]:
            row=deepcopy(self.rows[0]);row['registration_period'].update(starts_at=start,ends_at=stop)
            dates,times,next_date=registration_display(row,as_of=DAY)
            self.assertEqual(dates,UNKNOWN)
            self.assertEqual(next_date,NEXT_UNKNOWN)
            self.assertFalse(ISO.search(dates+times))

    def test_all_official_cards_really_render_and_legacy_values_do_not_crash_app(self):
        with patch('services.config.load_settings',return_value=Settings()):
            app=AppTest.from_file(str(ROOT/'gangseo_app.py')).run()
            for index,row in enumerate(self.rows):
                with self.subTest(record=row['id']):
                    state=new_state();state.update(references=[row],code='reference')
                    app.session_state['turns']=[{'user':'공식 정보 확인','state':state,'detail_first':True}]
                    app.session_state['turn_seq']=index+1
                    app.run()
                    self.assertFalse(app.exception)
                    self.assertEqual(app.chat_message[-1].subheader[0].value,row['name'])
                    self.assertFalse(ISO.search('\n'.join(x.value for x in app.chat_message[-1].markdown)))
            with patch('services.card_view.activity_facts',return_value=[('비용',None),('접수 기간','2026-08-18T09:00:00+09:00')]),self.assertLogs('services.card_view',level='WARNING'):
                app.run()
                self.assertFalse(app.exception)

class RelevanceTest(TestCase):
    def setUp(self):self.rows=load_activities()

    def test_walking_similar_closed_before_open_other_and_exact_first(self):
        options=related_options(self.rows,{'region':'강서구','activity_type':'걷기'},as_of=DAY)
        self.assertEqual([x['activity_type'] for x in options],['슬로우조깅','파크골프'])
        self.assertEqual([x['match_label'] for x in options],['유사 활동','다른 대안'])
        self.assertFalse(options[0]['available']);self.assertTrue(options[1]['available'])
        self.assertLess(alternative_rank('걷기','걷기',{},available=False),alternative_rank('걷기','슬로우조깅',{},available=True))
        row=deepcopy(self.rows[-4]);row.update(activity_type='걷기',id='fixture-exact-walking')
        state=handle_turn(new_state(),'강서구 걷기 프로그램 찾아줘',self.rows+[row],Settings(),as_of=DAY)
        self.assertEqual(state['results'][0]['id'],'fixture-exact-walking')
        self.assertFalse(state['alternatives'])

    def test_movement_purpose_effort_and_mobility_are_explicit_not_assumed_from_age(self):
        self.assertLess(alternative_rank('걷기','슬로우조깅',{}),alternative_rank('걷기','체조',{}))
        self.assertEqual(alternative_rank('걷기','슬로우조깅',{'effort_preference':'가볍게'}),alternative_rank('걷기','슬로우조깅',{}))
        self.assertEqual(alternative_rank('걷기','슬로우조깅',{'age':80}),alternative_rank('걷기','슬로우조깅',{'age':20}))
        self.assertEqual(alternative_rank('걷기','파크골프',{'mobility':'이동 적게'})[4],alternative_rank('걷기','파크골프',{})[4])
        self.assertGreater(alternative_rank('걷기','파크골프',{'purpose':'관람'})[1],alternative_rank('걷기','파크골프',{'purpose':'운동'})[1])

    def test_explicit_light_preference_survives_ai_failure_and_no_qualification_relaxation(self):
        from unittest.mock import Mock
        client=Mock();client.models.generate_content.side_effect=TimeoutError('private')
        state=handle_turn(new_state(),'강서구 가벼운 걷기 프로그램 찾아줘',self.rows,Settings(gemini_api_key='mock'),client=client,as_of=DAY)
        self.assertEqual(state['conditions']['effort_preference'],'가볍게')
        self.assertEqual(state['mode'],'fallback')
        self.assertEqual(state['alternatives'][0]['activity_type'],'슬로우조깅')
        self.assertIn('실제 강도',state['alternatives'][0]['reason'])
        limited=related_options(self.rows,{'region':'강서구','activity_type':'걷기','beginner':True,'time_slot':'오전','budget_amount':0},as_of=DAY)
        self.assertFalse(limited)

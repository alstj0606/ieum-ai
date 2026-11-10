"""Local fixtures only; invented neighbouring rows never enter production JSON."""
from copy import deepcopy
from datetime import date
from unittest import TestCase
from unittest.mock import Mock
from services.activities import load_activities, validate_activities
from services.config import Settings
from services.dialogue import new_state, handle_turn, choose_alternative, application_guide
from services.alternative_paths import adjacent_search, related_options
from services.recommendations import activity_facts

DAY = date(2026, 11, 10)

class AlternativePathsTest(TestCase):
    def setUp(self):
        self.rows=load_activities()

    def turn(self,state,text,**kwargs):
        return handle_turn(state,text,self.rows,Settings(),as_of=DAY,**kwargs)

    def walk(self):
        state=self.turn(new_state(),'가벼운 걷기 프로그램을 찾아주세요')
        self.assertEqual(state['pending'],'region')
        return self.turn(state,'서울 강서구요')

    def fixture(self,kind='걷기'):
        row=deepcopy(next(row for row in self.rows if row['activity_type']=='파크골프'))
        row.update(id='test-only-neighbour',region='서울특별시 양천구',activity_type=kind,name='TEST ONLY')
        return row

    def test_walking_gap_has_ranked_local_real_alternatives_and_one_question(self):
        state=self.walk()
        self.assertFalse(state['results'])
        self.assertEqual(state['pending'],'expand_region')
        self.assertEqual(state['message'].count('?'),1)
        self.assertEqual(state['alternatives'][0]['activity_type'],'파크골프')
        self.assertTrue(state['alternatives'][0]['available'])
        self.assertEqual(state['alternatives'][1]['activity_type'],'슬로우조깅')
        for option in state['alternatives']:
            for row in option['rows']:
                self.assertIn(row['id'],[x['id'] for x in self.rows])
                self.assertIn('강서구',row['region'])
        self.assertIn('강도',state['alternatives'][1]['reason'])

    def test_choose_alternative_keeps_profile_and_opens_actual_program(self):
        state=self.walk()
        state['conditions'].update(time_slot='오전',budget_amount=10000,budget_unit='회당',age=70,mobility='도보')
        # Recompute with the explicit profile before choosing.
        state=self.turn(state,'같은 조건으로 찾아줘')
        state=choose_alternative(state,'파크골프',self.rows,Settings(),as_of=DAY)
        self.assertFalse(state['results'])  # Fee unit cannot safely be compared with a per-visit budget.
        self.assertTrue(state['references'])
        for key,value in {'region':'강서구','time_slot':'오전','budget_amount':10000,'age':70,'mobility':'도보'}.items():
            self.assertEqual(state['conditions'][key],value)
        self.assertEqual(state['conditions']['activity_type'],'파크골프')
        self.assertEqual(state['references'][0]['activity_type'],'파크골프')
        state=choose_alternative(self.walk(),'파크골프',self.rows,Settings(),as_of=DAY)
        state=application_guide(state,self.rows,as_of=DAY)
        self.assertEqual(state['code'],'apply')
        self.assertIn('완료된 것은 아니',state['message'])

    def test_closed_alternative_is_reference_and_cannot_be_booked(self):
        state=choose_alternative(self.walk(),'슬로우조깅',self.rows,Settings(),as_of=DAY)
        self.assertFalse(state['results'])
        self.assertEqual(state['code'],'closed')
        self.assertEqual(dict(activity_facts(state['references'][0],as_of=DAY))['접수 상태'],'접수 마감')
        self.assertNotEqual(application_guide(state,self.rows,as_of=DAY)['code'],'apply')

    def test_no_consent_never_queries_neighbour_data(self):
        rows=self.rows+[self.fixture()]
        self.assertFalse(adjacent_search(rows,{'region':'강서구','activity_type':'걷기'},as_of=DAY)['results'])
        state=handle_turn(new_state(),'강서구 걷기 프로그램 찾아줘',rows,Settings(),as_of=DAY)
        self.assertFalse(state['results'])
        state=handle_turn(state,'아니요',rows,Settings(),as_of=DAY)
        self.assertEqual(state['code'],'expansion_declined')
        self.assertEqual(state['conditions']['region'],'강서구')
        self.assertFalse(state['expanded'])
        self.assertFalse(state['results'])

    def test_consent_uses_only_adjacent_official_fixture_and_allows_application(self):
        rows=self.rows+[self.fixture()]
        validate_activities(rows)
        state=handle_turn(new_state(),'강서구 걷기 프로그램 찾아줘',rows,Settings(),as_of=DAY)
        state=handle_turn(state,'네',rows,Settings(),as_of=DAY)
        self.assertEqual(state['code'],'expanded_found')
        self.assertEqual(state['results'][0]['id'],'test-only-neighbour')
        self.assertEqual(state['conditions']['region'],'강서구')
        self.assertEqual(application_guide(state,rows,as_of=DAY)['code'],'apply')

    def test_consent_without_data_says_missing_not_live_search_and_retains_local_options(self):
        state=self.turn(self.walk(),'네')
        self.assertEqual(state['code'],'expansion_empty')
        self.assertIn('자료가 아직 없어',state['message'])
        self.assertIn('실시간 웹 검색은 하지 않았어요',state['message'])
        self.assertTrue(state['alternatives'])
        self.assertFalse(state['results'])

    def test_beginner_qualification_time_and_budget_are_never_silently_relaxed(self):
        for profile in ({'beginner':True},{'time_slot':'저녁','budget_amount':0}):
            options=related_options(self.rows,dict(region='강서구',activity_type='걷기',**profile),as_of=DAY)
            self.assertNotIn('파크골프',[x['activity_type'] for x in options])

    def test_same_local_exact_match_has_priority_no_alternatives_or_expansion(self):
        state=self.turn(new_state(),'강서구 파크골프 프로그램 찾아줘')
        self.assertTrue(state['results'])
        self.assertFalse(state['alternatives'])
        self.assertIsNone(state['pending'])

    def test_failed_gemini_keeps_alternative_paths_and_safe_notice(self):
        client=Mock();client.models.generate_content.side_effect=TimeoutError('sensitive')
        state=handle_turn(new_state(),'강서구 걷기 프로그램 찾아줘',self.rows,Settings(gemini_api_key='mock'),client=client,as_of=DAY)
        self.assertEqual(state['mode'],'fallback')
        self.assertTrue(state['alternatives'])
        self.assertIn('Gemini',state['notice'])
        self.assertNotIn('sensitive',str(state))

    def test_unoffered_alternative_rejected_and_stale_activity_filter_removed(self):
        state=self.walk()
        with self.assertRaises(ValueError):choose_alternative(state,'made-up',self.rows,Settings(),as_of=DAY)
        state['conditions'].update(category='체육',tags=['걷기'])
        state=choose_alternative(state,'파크골프',self.rows,Settings(),as_of=DAY)
        self.assertTrue(state['results'])
        self.assertNotIn('tags',state['conditions'])

    def test_reference_fee_and_registration_unknown_remain_unknown(self):
        row=next(x for x in self.rows if x['activity_type']=='아쿠아로빅')
        facts=dict(activity_facts(row,as_of=DAY))
        self.assertEqual(facts['비용'],'공식 자료 확인 필요')
        self.assertIn('확인 필요',facts['접수 기간'])
        self.assertIn('확인 필요',facts['접수 상태'])

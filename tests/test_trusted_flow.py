"""End-to-end ordering/state contracts; official data only or explicit test fixtures."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import TestCase
from unittest.mock import Mock, patch
from streamlit.testing.v1 import AppTest
from services.activities import load_activities
from services.ai import empty_extraction
from services.config import Settings
from services.dialogue import new_state, handle_turn
from services.recommendation_pipeline import anchor_request, programme_options, prepare_view, adjacent_programmes, score_program, restore_local

DAY=date(2026,11,10)
ROOT=Path(__file__).resolve().parents[1]
QUERY='강서구 걷기 프로그램 찾아줘'

class TrustedFlowTest(TestCase):
    def setUp(self):self.rows=load_activities()
    def turn(self,state,text,**kwargs):return handle_turn(state,text,self.rows,Settings(),as_of=DAY,**kwargs)
    def walk(self):return self.turn(new_state(),QUERY)

    def test_first_choice_score_reason_consistent_and_no_parallel_duplicates(self):
        state=self.walk()
        self.assertEqual(state['recommendation_trace']['ordered_activities'],['슬로우조깅','파크골프'])
        scores=[o['score'] for o in state['alternatives']]
        self.assertEqual(scores,sorted(scores,reverse=True))
        self.assertFalse(state['ideas'])
        self.assertEqual(state['alternatives'][0]['match_label'],'유사 활동')
        self.assertLessEqual(state['alternatives'][0]['reason'].count('.'),2)
        self.assertIn('보행',state['alternatives'][0]['reason'])
        self.assertEqual(state['alternatives'][1]['match_label'],'다른 대안')

    def test_gemini_wrong_activity_is_anchored_to_explicit_user_request(self):
        payload=empty_extraction('search_program')
        payload['conditions'].update(region='양천구',activity_type='파크골프',category='문화·취미',tags=['파크골프'],time_slot='오전',residence='양천구',purpose='관람')
        payload['update_fields']=['region','activity_type','category','tags','time_slot','residence','purpose']
        client=Mock();client.models.generate_content.return_value=NS(prompt_feedback=None,candidates=[NS(finish_reason='STOP')],text=json.dumps(payload))
        state=handle_turn(new_state(),QUERY,self.rows,Settings(gemini_api_key='mock'),client=client,as_of=DAY)
        self.assertEqual(state['mode'],'gemini')
        self.assertEqual(state['conditions']['activity_type'],'걷기')
        self.assertEqual(state['conditions']['region'],'강서구')
        self.assertNotIn('time_slot',state['conditions'])
        self.assertNotIn('residence',state['conditions'])
        self.assertNotIn('purpose',state['conditions'])
        self.assertFalse(state['results'])
        self.assertEqual(state['alternatives'][0]['activity_type'],'슬로우조깅')

    def test_failed_gemini_uses_identical_pipeline(self):
        client=Mock();client.models.generate_content.side_effect=TimeoutError('private')
        state=handle_turn(new_state(),QUERY,self.rows,Settings(gemini_api_key='mock'),client=client,as_of=DAY)
        self.assertEqual(state['mode'],'fallback')
        self.assertEqual(state['alternatives'],self.walk()['alternatives'])
        self.assertIn('Gemini',state['notice'])

    def test_reversed_cached_candidates_are_sorted_again_and_deduplicated_at_view(self):
        state=self.walk();state['alternatives']=list(reversed(state['alternatives']))
        state['alternatives'].append(deepcopy(state['alternatives'][0]))
        state['alternatives'][0]['score']=99999
        state['alternatives'][0]['reason']='직접 일치한다는 잘못된 캐시'
        view=prepare_view(state,self.rows,user_text=QUERY,as_of=DAY)
        self.assertEqual([o['activity_type'] for o in view['alternatives']],['슬로우조깅','파크골프'])
        self.assertNotIn('직접 일치',view['alternatives'][1]['reason'])
        self.assertNotEqual(view['alternatives'][1]['score'],99999)
        self.assertEqual(state['alternatives'][0]['score'],99999)

    def test_explicit_aliases_correction_and_ambiguous_request_not_guessed(self):
        from services.recommendation_pipeline import explicit_activity
        self.assertEqual(explicit_activity('가벼운 걷는 활동 찾아줘'),'걷기')
        self.assertEqual(explicit_activity('걷기 말고 파크골프 찾아줘'),'파크골프')
        self.assertIsNone(explicit_activity('걷기와 수영 비교해줘'))
        self.assertEqual(explicit_activity('숲산책 프로그램'),'숲체험')
        for region in ('강서구','서울 강서구','서울강서구','서울특별시 강서구'):
            self.assertEqual(programme_options(self.rows,{'region':region,'activity_type':'걷기'},as_of=DAY)[0]['activity_type'],'슬로우조깅')
        self.assertNotIn('region',anchor_request('근처 수영장',empty_extraction())['update_fields'])

    def test_hard_conditions_preserved_and_scores_include_region_target_and_state(self):
        state=self.turn(new_state(),'강서구 오전 무료 걷기 프로그램 찾아줘')
        self.assertFalse(state['alternatives'])
        self.assertEqual(state['conditions']['time_slot'],'오전')
        self.assertEqual(state['conditions']['budget_amount'],0)
        request=empty_extraction('search_program');request['conditions']['time_slot']='오후';request['update_fields']=['time_slot']
        carried=self.turn(state,QUERY,extraction=request)
        self.assertEqual(carried['conditions']['time_slot'],'오전')
        row=next(r for r in self.rows if r['activity_type']=='슬로우조깅')
        score=score_program(row,{'activity_type':'걷기','region':'강서구','age':70,'residence':'강서구'},as_of=DAY)
        self.assertEqual(score['score'],sum(score['score_parts'].values()))
        self.assertEqual(score['score_parts']['region'],10)
        self.assertEqual(score['score_parts']['target'],5)
        self.assertEqual(score['score_parts']['registration'],0)
        self.assertGreater(score['score_parts']['activity'],100)

    def test_adjacent_empty_clears_new_cards_but_retains_explicit_history(self):
        local=self.walk();state=self.turn(local,'네')
        self.assertEqual(state['flow'],'adjacent')
        self.assertEqual(state['search_scope']['kind'],'adjacent')
        self.assertEqual(state['search_scope']['covered'],[])
        for field in ('results','references','alternatives','ideas','facilities','adjacent_groups'):self.assertFalse(state[field])
        self.assertIn('현재 확인된 인접 지역 프로그램 자료가 없습니다',state['message'])
        self.assertEqual(state['previous_local']['alternatives'],local['alternatives'])
        state=restore_local(state,self.rows,as_of=DAY)
        self.assertEqual(state['flow'],'program')
        self.assertEqual(state['alternatives'][0]['activity_type'],'슬로우조깅')

    def test_consent_decline_never_widens_and_adjacent_followup_stays_separate(self):
        state=self.turn(self.walk(),'아니요')
        self.assertFalse(state['expanded'])
        state=self.turn(self.walk(),'네')
        state=self.turn(state,'오후 말고 오전으로 찾아줘')
        self.assertEqual(state['flow'],'adjacent')
        self.assertEqual(state['conditions']['time_slot'],'오전')
        self.assertFalse(state['results'])
        state=self.turn(state,'강서구 걷기 프로그램 찾아줘')
        self.assertEqual(state['flow'],'program')

    def test_legacy_empty_expansion_cannot_redisplay_gangseo_as_neighbour(self):
        state=self.walk();state.update(code='expansion_empty',expansion_consent='강서구');state.pop('search_scope',None)
        view=prepare_view(state,self.rows,as_of=DAY)
        self.assertEqual(view['flow'],'adjacent')
        self.assertFalse(view['alternatives']);self.assertFalse(view['references'])
        self.assertIn('현재 확인된 인접 지역 프로그램 자료가 없습니다',view['message'])

    def test_only_authorized_real_district_rows_are_grouped_and_scored(self):
        fixture=deepcopy(next(r for r in self.rows if r['activity_type']=='파크골프'))
        fixture.update(id='fixture-yangcheon-walk',region='서울특별시 양천구',activity_type='걷기')
        second=deepcopy(fixture);second.update(id='fixture-mapo-gym',region='서울특별시 마포구',activity_type='체조')
        rows=self.rows+[fixture,second]
        self.assertFalse(adjacent_programmes(rows,{'region':'강서구','activity_type':'걷기'},as_of=DAY)['results'])
        outcome=adjacent_programmes(rows,{'region':'강서구','activity_type':'걷기'},consent=True,as_of=DAY)
        self.assertEqual(set(outcome['covered']),{'양천구','마포구'})
        all_rows=outcome['results']+outcome['references']
        self.assertEqual(all_rows[0]['id'],'fixture-yangcheon-walk')
        self.assertNotIn('강서구',{r['region'] for r in all_rows})
        self.assertEqual(len({r['id'] for r in all_rows}),len(all_rows))
        self.assertEqual(len(outcome['groups']),2)

    def test_app_first_button_matches_score_order_even_with_reversed_legacy_state(self):
        with patch('services.config.load_settings',return_value=Settings()):
            app=AppTest.from_file(str(ROOT/'app.py')).run()
            state=self.walk();state['alternatives'].reverse()
            app.session_state['dialog']=state
            app.session_state['turns']=[{'user':QUERY,'state':state}]
            app.session_state['turn_seq']=1
            app.run();self.assertFalse(app.exception)
            choices=[b.label for b in app.chat_message[-1].button]
            self.assertEqual(choices[0],'슬로우조깅 정보 보기 →')
            self.assertFalse(any('알아보기' in label for label in choices))
            app.button(key='expand_yes').click().run()
            self.assertFalse(app.exception)
            self.assertFalse(app.chat_message[-1].subheader)
            self.assertEqual(app.chat_message[-1].button[0].label,'강서구 추천 다시 보기')

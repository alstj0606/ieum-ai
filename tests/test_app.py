"""Single-chat UI regression tests; all provider calls are mocked."""
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
import json
from streamlit.testing.v1 import AppTest
from services.activities import load_activities
from services.ai import empty_extraction
from services.config import Settings
from services.dialogue import manual_search, new_state
from services.voice import VoiceError

APP=str(Path(__file__).resolve().parents[1]/"app.py")
DAY=date(2026,11,9)

class AppFlowTest(TestCase):
    def test_manual_search_and_official_values_with_no_key(self):
        with patch('services.config.load_settings',return_value=Settings()):
            app=AppTest.from_file(APP).run()
            app.selectbox(key='manual_category').select('문화·취미')
            app.selectbox(key='manual_time').select('오전')
            app.button(key='manual_submit').click().run()
            self.assertFalse(app.exception)
            state=app.session_state['dialog']
            self.assertTrue(state['results'])
            self.assertLessEqual(len(state['results']),3)
            for row in state['results']:
                self.assertTrue(any(row['name']==item.value for item in app.chat_message[-1].subheader))
                self.assertTrue(any(row['schedule']['text'].replace('~', '\\~') in item.value for item in app.chat_message[-1].markdown))
            before=state['results']
            app.button(key='demo_example').click().run()
            self.assertEqual(app.session_state['dialog']['results'],before)
            self.assertTrue(any('가상 프로그램' in item.value for item in app.subheader))

    def test_ai_submit_calls_once_and_failure_keeps_dialogue(self):
        payload=empty_extraction()
        payload['conditions'].update(region='강서구',activity_type='가드닝')
        payload['update_fields']=['region','activity_type']
        client=Mock()
        client.models.generate_content.return_value=SimpleNamespace(candidates=[SimpleNamespace(finish_reason='STOP')],prompt_feedback=None,text=json.dumps(payload,ensure_ascii=False))
        with patch('services.config.load_settings',return_value=Settings(gemini_api_key='mock-intent-only',api_key='mock-test-only')),patch('services.ai.make_client',return_value=client):
            app=AppTest.from_file(APP).run()
            app.chat_input(key='chat').set_value('강서구 식물 키우기').run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['dialog']['code'],'found')
            app.run()
            self.assertEqual(client.models.generate_content.call_count,1)
            before=app.session_state['dialog']['conditions']
            client.models.generate_content.side_effect=TimeoutError('sensitive response')
            app.chat_input(key='chat').set_value('다른 시간에요').run()
            self.assertEqual(app.session_state['dialog']['conditions'],before)
            self.assertEqual(app.session_state['turns'][-1]['user'],'다른 시간에요')
            self.assertEqual(app.session_state['dialog']['mode'],'fallback')
            self.assertEqual(app.session_state['dialog']['diagnostic']['code'],'timeout')
            self.assertTrue(any('기본 규칙' in x.value for x in app.info))
            self.assertFalse(any('sensitive response' in x.value for x in app.warning))

    def test_stt_failure_allows_text_search(self):
        recording=SimpleNamespace(name='question.wav',getvalue=lambda:b'test')
        with patch('services.config.load_settings',return_value=Settings()),patch('services.voice.transcribe',side_effect=VoiceError('음성 인식 실패')):
            with patch('streamlit.chat_input',side_effect=[SimpleNamespace(audio=recording),None]):
                app=AppTest.from_file(APP).run()
            self.assertFalse(app.exception)
            self.assertTrue(any('음성 인식 실패' in x.value for x in app.warning))
            app.run()
            app.chat_input(key='chat').set_value('강서구 국악').run()
            self.assertTrue(app.session_state['dialog']['results'])

    def seed(self,app):
        state=manual_search(new_state(),load_activities(),as_of=DAY)
        app.session_state['dialog']=state
        app.session_state['turns']=[{'user':'공식 활동 찾아줘','state':state}]
        app.session_state['turn_seq']=1
        app.run()
        return state

    def test_tts_failure_preserves_results_and_stop_clears_media(self):
        with patch('services.config.load_settings',return_value=Settings(gemini_api_key='mock-intent-only',api_key='mock-test-only')),patch('services.voice.synthesize',side_effect=VoiceError('음성 안내 실패')) as synth:
            app=AppTest.from_file(APP).run()
            self.seed(app)
            app.button(key='listen_0').click().run()
            self.assertTrue(app.session_state['dialog']['results'])
            self.assertTrue(any('음성 안내 실패' in x.value for x in app.warning))
            synth.side_effect=None;synth.return_value=b'mock-audio'
            app.button(key='listen_0').click().run()
            self.assertTrue(app.session_state['speech'])
            app.button(key='stop_speech').click().run()
            self.assertIsNone(app.session_state['speech'])

    def test_second_selection_reads_selected_activity(self):
        with patch('services.config.load_settings',return_value=Settings(gemini_api_key='mock-intent-only',api_key='mock-test-only')),patch('services.voice.synthesize',return_value=b'mock-audio') as synth:
            app=AppTest.from_file(APP).run()
            state=self.seed(app)
            selected=state['results'][1]
            app.button(key=f"apply_{selected['id']}").click().run()
            app.button(key='listen_1').click().run()
            self.assertFalse(app.exception)
            spoken=synth.call_args.args[0]
            self.assertIn(selected['name'],spoken)
            self.assertNotIn(state['results'][0]['name'],spoken)

    def test_voice_auto_search_once_transcript_edit_and_slow_repeat(self):
        recording=SimpleNamespace(name='question.wav',getvalue=lambda:b'test')
        with patch('services.config.load_settings',return_value=Settings()),patch('services.voice.transcribe',return_value='강서구 국악') as stt,patch('services.voice.synthesize',return_value=b'mock') as tts:
            with patch('streamlit.chat_input',side_effect=[SimpleNamespace(audio=recording),None]):
                app=AppTest.from_file(APP).run()
            self.assertFalse(app.exception)
            self.assertTrue(app.session_state['dialog']['results'])
            app.run()
            self.assertEqual(stt.call_count,1)
            self.assertEqual(tts.call_count,1)
            app.button(key='edit_transcript').click().run()
            self.assertEqual(app.text_area(key='corrected').value,'강서구 국악')
            before=app.session_state['dialog']['conditions']
            app.chat_input(key='chat').set_value('천천히 알려줘').run()
            self.assertEqual(tts.call_args.kwargs['speed'],0.7)
            self.assertEqual(app.session_state['dialog']['conditions'],before)

    def test_followup_conditions_and_application_stay_in_chat(self):
        with patch('services.config.load_settings',return_value=Settings()):
            app=AppTest.from_file(APP).run()
            app.chat_input(key='chat').set_value('국악 공연').run()
            self.assertEqual(app.session_state['dialog']['pending'],'region')
            app.button(key='choose_region').click().run()
            self.assertTrue(app.session_state['dialog']['results'])
            app.chat_input(key='chat').set_value('신청 방법 알려줘').run()
            self.assertEqual(app.session_state['dialog']['code'],'apply')
            self.assertEqual(len(app.chat_message),6)
            self.assertTrue(any('완료된 것은 아니에요' in x.value for x in app.chat_message[-1].markdown))

    def test_new_recording_replaces_previous_correction_draft(self):
        recording=SimpleNamespace(name='question.wav',getvalue=lambda:b'test')
        with patch('services.config.load_settings',return_value=Settings()), \
                patch('services.voice.transcribe',side_effect=['강서구 국악','강서구 가드닝']), \
                patch('services.voice.synthesize',return_value=b'mock'):
            with patch('streamlit.chat_input',side_effect=[SimpleNamespace(audio=recording),None]):
                app=AppTest.from_file(APP).run()
            app.run()
            app.button(key='edit_transcript').click().run()
            app.text_area(key='corrected').input('이전 음성의 수정 초안').run()
            with patch('streamlit.chat_input',side_effect=[SimpleNamespace(audio=recording),None]):
                app.run()
            self.assertFalse(app.session_state['edit_voice'])
            app.run()
            app.button(key='edit_transcript').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.text_area(key='corrected').value,'강서구 가드닝')

    def test_automatic_tts_failure_keeps_results_without_retrying_on_rerun(self):
        recording=SimpleNamespace(name='question.wav',getvalue=lambda:b'test')
        with patch('services.config.load_settings',return_value=Settings()), \
                patch('services.voice.transcribe',return_value='강서구 국악'), \
                patch('services.voice.synthesize',side_effect=VoiceError('음성 안내 실패')) as tts:
            with patch('streamlit.chat_input',side_effect=[SimpleNamespace(audio=recording),None]):
                app=AppTest.from_file(APP).run()
            app.run()
            self.assertFalse(app.exception)
            self.assertTrue(app.session_state['dialog']['results'])
            self.assertEqual(app.session_state['transcript'],'강서구 국악')
            self.assertTrue(any('음성 안내 실패' in x.value for x in app.warning))
            self.assertEqual(tts.call_count,1)

    def test_reported_question_auth_failure_shows_safe_fallback_inside_chat(self):
        from google.genai.errors import ClientError
        client=Mock()
        client.models.generate_content.side_effect=ClientError(401,{'error':{'message':'private-provider-canary'}})
        text='강서구에서 어르신이 참여할 수 있는 운동을 추천해줘'
        with patch('services.config.load_settings',return_value=Settings(gemini_api_key='mock-intent-only',api_key='mock-test-only')),patch('services.ai.make_client',return_value=client):
            app=AppTest.from_file(APP).run()
            app.chat_input(key='chat').set_value(text).run()
            self.assertFalse(app.exception)
            state=app.session_state['dialog']
            self.assertEqual(state['diagnostic']['code'],'authentication')
            self.assertTrue(state['ideas'])
            self.assertEqual(state['code'],'ideas')
            self.assertEqual(app.session_state['turns'][-1]['user'],text)
            self.assertTrue(any('기본 규칙' in x.value for x in app.chat_message[-1].info))
            self.assertFalse(any('private-provider-canary' in x.value for x in app.markdown))

    def test_gemini_only_key_supports_text_without_openai_voice(self):
        payload=empty_extraction()
        payload['conditions'].update(region='강서구',activity_type='국악공연')
        payload['update_fields']=['region','activity_type']
        client=Mock()
        client.models.generate_content.return_value=SimpleNamespace(
            candidates=[SimpleNamespace(finish_reason='STOP')],prompt_feedback=None,text=json.dumps(payload))
        with patch('services.config.load_settings',return_value=Settings(gemini_api_key='gemini-only')), \
                patch('services.ai.make_client',return_value=client), \
                patch('services.voice.make_voice_client') as voice:
            app=AppTest.from_file(APP).run()
            self.assertTrue(any('Gemini' in x.value and 'OpenAI' in x.value for x in app.caption))
            app.chat_input(key='chat').set_value('강서구 국악').run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['dialog']['mode'],'gemini')
            self.assertTrue(app.session_state['dialog']['results'])
            self.assertTrue(app.button(key='listen_0').disabled)
            voice.assert_not_called()

    def test_openai_voice_key_does_not_enable_gemini_intent(self):
        with patch('services.config.load_settings',return_value=Settings(api_key='voice-only')), \
                patch('services.ai.make_client') as gemini:
            app=AppTest.from_file(APP).run()
            app.chat_input(key='chat').set_value('강서구 국악').run()
            self.assertEqual(app.session_state['dialog']['mode'],'basic')
            self.assertEqual(app.session_state['dialog']['diagnostic']['code'],'key_missing')
            self.assertTrue(app.session_state['dialog']['results'])
            gemini.assert_not_called()

    def test_model_inspection_preserves_dialogue_and_does_not_generate(self):
        report={'model':'gemini-2.5-flash','model_source':'기본값',
                'api_base':'https://generativelanguage.googleapis.com','api_version':'v1beta',
                'model_setting':'ok','metadata_code':'metadata_ok','list_code':'list_ok',
                'custom_base_ignored':False,'models':['gemini-2.5-flash']}
        with patch('services.config.load_settings',return_value=Settings(gemini_api_key='mock')),\
                patch('services.model_probe.inspect_models',return_value=report) as probe,\
                patch('services.ai.make_client') as generate:
            app=AppTest.from_file(APP).run()
            self.seed(app)
            before=app.session_state['dialog']
            app.button(key='inspect_models').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['dialog'],before)
            self.assertEqual(len(app.session_state['turns']),1)
            probe.assert_called_once()
            generate.assert_not_called()

    def test_fixed_generation_probe_preserves_user_conversation_and_hides_body(self):
        report={'model':'gemini-2.5-flash','api_base':'https://generativelanguage.googleapis.com',
                'path':'/v1beta/models/gemini-2.5-flash:generateContent',
                'simple_code':'ok','structured_code':'generation_not_found','comparison':'structured_failed'}
        with patch('services.config.load_settings',return_value=Settings(gemini_api_key='mock')), \
                patch('services.generation_probe.inspect_generation',return_value=report) as probe:
            app=AppTest.from_file(APP).run()
            self.seed(app)
            before=app.session_state['dialog']
            app.button(key='inspect_generation').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['dialog'],before)
            self.assertEqual(len(app.session_state['turns']),1)
            self.assertTrue(any('단순 생성: ok' in x.value for x in app.markdown))
            self.assertTrue(any('구조화 추출: generation_not_found' in x.value for x in app.markdown))
            probe.assert_called_once()

    def test_general_idea_button_continues_chat_and_program_no_match_offers_choices(self):
        with patch('services.config.load_settings',return_value=Settings()):
            app=AppTest.from_file(APP).run()
            app.chat_input(key='chat').set_value('노인이 할 수 있는 운동 추천해 줘').run()
            self.assertEqual(app.session_state['dialog']['code'],'ideas')
            self.assertTrue(any('일반 활동 제안' in x.value for x in app.chat_message[-1].markdown))
            app.button(key='idea_water').click().run()
            self.assertEqual(app.session_state['dialog']['conditions']['activity_type'],'아쿠아로빅')
            self.assertEqual(app.session_state['dialog']['pending'],'region')
            app.button(key='choose_region').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['dialog']['code'],'unknown')
            self.assertTrue(app.session_state['dialog']['ideas'])
            self.assertFalse(app.session_state['dialog']['results'])

    def test_facility_answer_has_source_and_verification_without_program_booking(self):
        with patch('services.config.load_settings',return_value=Settings()):
            app=AppTest.from_file(APP).run()
            app.chat_input(key='chat').set_value('근처 수영장 찾아줘').run()
            app.button(key='choose_region').click().run()
            state=app.session_state['dialog']
            self.assertEqual(state['code'],'facilities')
            self.assertTrue(any('현재 이용 가능 여부 미확인' in x.value for x in app.chat_message[-1].markdown))
            self.assertTrue(any('확인일:' in x.value for x in app.chat_message[-1].markdown))
            self.assertFalse(any(x.key and x.key.startswith('apply_') for x in app.button))

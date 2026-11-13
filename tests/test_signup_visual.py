"""The visual experiment is inert, step-scoped, and honest about verification."""
from copy import deepcopy
from html.parser import HTMLParser
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch
from streamlit.testing.v1 import AppTest
from services.config import Settings
from services.institution_dialogue import load_institution, new_institution_state, guide_turn
from ui.signup_visual import visual_guide_html


class Tags(HTMLParser):
    def __init__(self):
        super().__init__(); self.tags=[]
    def handle_starttag(self,tag,attrs):
        self.tags.append(tag)


class SignupVisualTest(TestCase):
    def test_only_one_known_stage_without_interactive_imitation(self):
        data=load_institution()
        for step in data['signup_steps']:
            with self.subTest(step=step['step_id']):
                markup=visual_guide_html(step); parser=Tags(); parser.feed(markup)
                self.assertEqual(parser.tags.count('section'),1)
                self.assertFalse(set(parser.tags)&{'iframe','script','input','form','button','a','img'})
                self.assertIn('실제 사이트 아님',markup)
                self.assertIn('실제 배치·크기와 달라요',markup)
                self.assertIn(step['step_id'],markup)
                self.assertNotIn('onclick',markup)

    def test_text_is_escaped_and_unverified_step_is_not_drawn(self):
        step=deepcopy(load_institution()['signup_steps'][2]); step['button_label']='<script>bad()</script>'
        self.assertNotIn('<script>',visual_guide_html(step)); self.assertIn('&lt;script&gt;',visual_guide_html(step))
        step['step_id']='after_authentication'
        self.assertEqual(visual_guide_html(step),'')

    def test_header_access_failure_is_not_presented_as_site_frame_denial(self):
        verified=load_institution()['visual_guide_verification']
        self.assertFalse(verified['headers_verified']); self.assertEqual(verified['embedding_status'],'unverified')
        self.assertIsNone(verified['response_headers']['x_frame_options'])
        self.assertIsNone(verified['response_headers']['content_security_policy'])
        self.assertIn('CONNECT 403',verified['http_probe_result']); self.assertIn('미검증',verified['after_authentication'])

    def test_help_stays_on_current_step_with_or_without_gemini(self):
        for has_api in (False,True):
            state=guide_turn(new_institution_state(),'복지관 회원이고 아이디가 없어요',Settings())
            state['index']=2
            client=Mock(); client.models.generate_content.side_effect=TimeoutError('private response')
            for utterance in ('버튼이 안 보여요','어디를 눌러요?'):
                state=guide_turn(state,utterance,Settings(gemini_api_key='mock' if has_api else ''),client=client)
                self.assertEqual(state['index'],2); self.assertEqual(state['guide_kind'],'signup')
                self.assertIn('아래쪽',state['message']); self.assertNotIn('private response',str(state))
                self.assertEqual(state['mode'],'fallback' if has_api else 'basic')
                self.assertNotIn('authenticated',state); self.assertNotIn('results',state)

    def test_streamlit_opt_in_navigation_and_no_completion_inference(self):
        root=Path(__file__).resolve().parents[1]
        with patch('ui.seongsan_app.load_settings',return_value=Settings()):
            app=AppTest.from_file(str(root/'institution_app.py'),default_timeout=15).run()
            self.assertFalse(app.exception)
            app.button(key='inst_start_visual').click().run()
            self.assertIsNone(app.session_state['institution_session']['membership'])
            self.assertIsNone(app.session_state['institution_session']['online_account'])
            self.assertEqual(app.session_state['institution_session']['guide_kind'],'application')
            app.button(key='inst_member').click().run()
            app.button(key='inst_no_id').click().run()
            self.assertTrue(app.toggle(key='inst_visual_guide').value)
            app.button(key='inst_next').click().run()
            self.assertEqual(app.session_state['institution_session']['index'],1)
            app.toggle(key='inst_visual_guide').set_value(False).run()
            self.assertEqual(app.session_state['institution_session']['index'],1)
            app.toggle(key='inst_visual_guide').set_value(True).run()
            app.button(key='inst_next').click().run(); app.button(key='inst_previous').click().run(); app.run()
            self.assertEqual(app.session_state['institution_session']['index'],1)
            self.assertTrue(app.toggle(key='inst_visual_guide').value)
            for _ in range(3):app.button(key='inst_next').click().run()
            self.assertTrue(app.button(key='inst_next').disabled)
            self.assertNotIn('authenticated',app.session_state['institution_session'])
            app.button(key='inst_reset').click().run()
            self.assertEqual(app.session_state['institution_session']['guide_kind'],'application')
            self.assertFalse(app.exception)

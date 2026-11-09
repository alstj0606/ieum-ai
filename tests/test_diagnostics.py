"""Actual Gemini SDK error/config objects; no real Google or OpenAI request."""
from copy import deepcopy
from datetime import date
from types import SimpleNamespace as NS
from unittest import TestCase
from unittest.mock import Mock, patch
import json
import os
import httpx2
from google.genai import errors, types
from jsonschema import Draft202012Validator
from services.ai import AIError, SCHEMA, empty_extraction, extract_conditions, make_client
from services.config import Settings, load_settings
from services.activities import load_activities
from services.dialogue import handle_turn, new_state
from services.voice import make_voice_client

SECRET='provider-private-canary-no-log'
DAY=date(2026,11,9)

class DiagnosticsTest(TestCase):
    def test_sdk_errors_are_classified_without_exposing_raw_bodies(self):
        cases=[(errors.ClientError(401,{'error':{'message':SECRET}}),'authentication'),
               (errors.ClientError(400,{'error':{'message':SECRET,'details':[{'reason':'API_KEY_INVALID'}]}}),'authentication'),
               (errors.ClientError(403,{'error':{'message':SECRET}}),'permission'),
               (errors.ClientError(429,{'error':{'message':SECRET,'status':'RESOURCE_EXHAUSTED'}}),'rate_limit'),
               (errors.ClientError(404,{'error':{'message':SECRET}}),'model_access'),
               (errors.ClientError(400,{'error':{'message':SECRET}}),'request'),
               (errors.ServerError(503,{'error':{'message':SECRET}}),'service'),
               (httpx2.ReadTimeout(SECRET),'timeout'),(httpx2.ConnectError(SECRET),'connection'),
               (RuntimeError(SECRET),'unknown')]
        for error,code in cases:
            with self.subTest(code=code):
                client=Mock();client.models.generate_content.side_effect=error
                with self.assertRaises(AIError) as caught:
                    extract_conditions('강서구 운동',new_state(),load_activities(),Settings(),client=client)
                self.assertEqual(caught.exception.code,code)
                self.assertNotIn(SECRET,str(caught.exception))
                state=handle_turn(new_state(),'강서구 운동',load_activities(),Settings(gemini_api_key='mock'),client=client,as_of=DAY)
                self.assertEqual(state['diagnostic'],{'code':code})
                self.assertEqual(state['mode'],'fallback')
                self.assertTrue(state['results'])
                self.assertNotIn(SECRET,json.dumps(state,ensure_ascii=False))

    def test_missing_key_configuration_and_sdk_timeout(self):
        with patch.dict(os.environ,{'GEMINI_MODEL':'   ','GEMINI_API_KEY':'','OPENAI_API_KEY':'voice-only','OPENAI_MODEL':'ignored'}):
            settings=load_settings({'GEMINI_API_KEY':'gemini-only'})
            self.assertEqual(settings.model,'gemini-2.5-flash')
            self.assertEqual(settings.api_key,'voice-only')
            self.assertEqual(settings.gemini_api_key,'gemini-only')
            self.assertNotIn('gemini-only',repr(settings))
            self.assertNotIn('voice-only',repr(settings))
        with self.assertRaises(AIError) as caught:
            make_client(Settings(api_key='OpenAI-cannot-authorize-Gemini'))
        self.assertEqual(caught.exception.code,'key_missing')
        with patch('google.genai.Client',side_effect=ValueError(SECRET)):
            with self.assertRaises(AIError) as caught:make_client(Settings(gemini_api_key='mock'))
        self.assertEqual(caught.exception.code,'configuration')
        with patch('google.genai.Client') as factory:
            make_client(Settings(gemini_api_key='gemini-only',api_key='openai-voice'))
            self.assertEqual(factory.call_args.kwargs['api_key'],'gemini-only')
            options=factory.call_args.kwargs['http_options']
            self.assertEqual(options.timeout,30000)
            self.assertEqual(options.retry_options.attempts,1)
            self.assertFalse(factory.call_args.kwargs['vertexai'])
        with patch('openai.OpenAI') as factory:
            make_voice_client(Settings(gemini_api_key='gemini-only',api_key='openai-voice'))
            self.assertEqual(factory.call_args.kwargs['api_key'],'openai-voice')

    def test_structured_response_failures_are_distinct(self):
        cases=[(NS(candidates=[NS(finish_reason='MAX_TOKENS')],prompt_feedback=None),'output_limit'),
               (NS(candidates=[NS(finish_reason='OTHER')],prompt_feedback=None),'incomplete'),
               (NS(candidates=[],prompt_feedback=NS(block_reason='SAFETY')),'refused'),
               (NS(candidates=[NS(finish_reason='SAFETY')],prompt_feedback=None),'refused'),
               (NS(candidates=[],prompt_feedback=None),'response_format')]
        for text in ('not json','{"program":"invented"}',''):
            cases.append((NS(candidates=[NS(finish_reason='STOP')],prompt_feedback=None,text=text),'response_format'))
        for response,code in cases:
            with self.subTest(code=code):
                client=Mock();client.models.generate_content.return_value=response
                with self.assertRaises(AIError) as caught:extract_conditions('질문',new_state(),load_activities(),Settings(),client=client)
                self.assertEqual(caught.exception.code,code)

    def test_valid_schema_and_verified_model_reasoning_options(self):
        Draft202012Validator.check_schema(SCHEMA)
        payload=empty_extraction();payload['conditions']['region']='강서구';payload['update_fields']=['region']
        Draft202012Validator(SCHEMA).validate(payload)
        for model in (Settings.model,'gemini-custom-unknown'):
            client=Mock();client.models.generate_content.return_value=NS(candidates=[NS(finish_reason='STOP')],prompt_feedback=NS(block_reason='BLOCK_REASON_UNSPECIFIED'),text=json.dumps(payload))
            self.assertEqual(extract_conditions('강서구',new_state(),load_activities(),Settings(model=model),client=client),payload)
            call=client.models.generate_content.call_args.kwargs
            config=call['config']
            self.assertEqual(config.response_json_schema,SCHEMA)
            self.assertEqual(config.response_mime_type,'application/json')
            self.assertEqual(config.max_output_tokens,2000)
            self.assertEqual(config.thinking_config.thinking_budget if config.thinking_config else None,0 if model==Settings.model else None)
            self.assertNotIn('official_url',call['contents'])
            self.assertNotIn('fee_amount',call['contents'])
            self.assertIsNone(config.tools)

    def test_reported_question_falls_back_to_official_exercise_without_inventing_age(self):
        text='강서구에서 어르신이 참여할 수 있는 운동을 추천해줘'
        client=Mock();client.models.generate_content.side_effect=TimeoutError(SECRET)
        state=handle_turn(new_state(),text,load_activities(),Settings(gemini_api_key='mock'),client=client,as_of=DAY)
        self.assertEqual(state['conditions'],{'region':'강서구','category':'체육'})
        self.assertTrue(state['results'])
        self.assertTrue(all(x['category']=='체육' for x in state['results']))
        self.assertEqual(state['history'][-2]['content'],text)
        self.assertLessEqual(len(state['results']),3)

    def test_unrecognized_fallback_keeps_history_and_conditions_without_reusing_stale_cards(self):
        previous=handle_turn(new_state(),'강서구 국악',load_activities(),Settings(),as_of=DAY)
        before=deepcopy(previous)
        client=Mock();client.models.generate_content.side_effect=TimeoutError()
        state=handle_turn(previous,'새로운 취향을 알아주세요',load_activities(),Settings(gemini_api_key='mock'),client=client,as_of=DAY)
        self.assertEqual(previous,before)
        self.assertEqual(state['conditions'],before['conditions'])
        self.assertEqual(state['history'][:-2],before['history'])
        self.assertEqual(state['results'],[])
        self.assertEqual(state['code'],'clarify')

    def test_owned_gemini_client_closes_after_failure(self):
        client=Mock();client.models.generate_content.side_effect=errors.ServerError(503,{'error':{'message':SECRET}})
        with patch('services.ai.make_client',return_value=client):
            with self.assertRaises(AIError):
                extract_conditions('강서구',new_state(),load_activities(),Settings(gemini_api_key='mock'))
        client.close.assert_called_once()

    def test_real_sdk_http_transport_preserves_schema_and_provider_key(self):
        from google import genai
        payload=empty_extraction()
        calls=[]
        def handler(request):
            calls.append(request)
            body=json.loads(request.content)
            self.assertEqual(request.headers['x-goog-api-key'],'gemini-mock-only')
            self.assertIn('gemini-2.5-flash:generateContent',str(request.url))
            self.assertEqual(body['generationConfig']['responseJsonSchema'],SCHEMA)
            self.assertEqual(body['generationConfig']['thinkingConfig'].get('thinking_budget',body['generationConfig']['thinkingConfig'].get('thinkingBudget')),0)
            return httpx2.Response(200,json={'candidates':[{'content':{'role':'model','parts':[{'text':json.dumps(payload)}]},'finishReason':'STOP'}]})
        with httpx2.Client(transport=httpx2.MockTransport(handler)) as http:
            with genai.Client(api_key='gemini-mock-only',vertexai=False,enterprise=False,
                    http_options=types.HttpOptions(api_version='v1beta',httpx_client=http,
                                                   retry_options=types.HttpRetryOptions(attempts=1))) as client:
                self.assertEqual(extract_conditions('강서구',new_state(),load_activities(),Settings(),client=client),payload)
        self.assertEqual(len(calls),1)

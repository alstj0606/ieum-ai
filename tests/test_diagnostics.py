"""SDK exception objects and HTTP mocks only; never call the real OpenAI API."""
from copy import deepcopy
from datetime import date
from types import SimpleNamespace as NS
from unittest import TestCase
from unittest.mock import Mock, patch
import json
import httpx2 as httpx
import openai
from jsonschema import Draft202012Validator
from services.ai import AIError, SCHEMA, empty_extraction, extract_conditions, make_client
from services.config import Settings, load_settings
from services.diagnostics import DIAGNOSTICS
from services.activities import load_activities
from services.dialogue import handle_turn, new_state

SECRET='provider-private-canary-no-log'
REQUEST=httpx.Request('POST','https://api.openai.com/v1/responses')
DAY=date(2026,11,9)


def sdk_error(cls,status,code=None):
    return cls(SECRET,response=httpx.Response(status,request=REQUEST),body={'message':SECRET,'code':code})

class DiagnosticsTest(TestCase):
    def test_sdk_errors_are_classified_without_exposing_raw_bodies(self):
        cases=[
            (sdk_error(openai.AuthenticationError,401),'authentication'),
            (sdk_error(openai.PermissionDeniedError,403),'permission'),
            (sdk_error(openai.RateLimitError,429,'insufficient_quota'),'quota'),
            (sdk_error(openai.RateLimitError,429,'rate_limit_exceeded'),'rate_limit'),
            (sdk_error(openai.NotFoundError,404,'model_not_found'),'model_access'),
            (sdk_error(openai.BadRequestError,400,'invalid_json_schema'),'request_schema'),
            (sdk_error(openai.BadRequestError,400,'unsupported_parameter'),'request_parameter'),
            (sdk_error(openai.BadRequestError,400),'request'),
            (sdk_error(openai.InternalServerError,503),'service'),
            (openai.APITimeoutError(request=REQUEST),'timeout'),
            (openai.APIConnectionError(message=SECRET,request=REQUEST),'connection'),
            (RuntimeError(SECRET),'unknown'),
        ]
        for error,code in cases:
            with self.subTest(code=code):
                client=Mock();client.responses.create.side_effect=error
                with self.assertRaises(AIError) as caught:
                    extract_conditions('강서구 운동',new_state(),load_activities(),Settings(api_key='mock'),client=client)
                self.assertEqual(caught.exception.code,code)
                self.assertNotIn(SECRET,str(caught.exception))
                state=handle_turn(new_state(),'강서구 운동',load_activities(),Settings(api_key='mock'),client=client,as_of=DAY)
                self.assertEqual(state['diagnostic'],{'code':code})
                self.assertEqual(state['mode'],'fallback')
                self.assertTrue(state['results'])
                self.assertNotIn(SECRET,json.dumps(state,ensure_ascii=False))

    def test_missing_key_configuration_and_sdk_timeout(self):
        import os
        with patch.dict(os.environ, {'OPENAI_MODEL':'   '}):
            self.assertEqual(load_settings().model, Settings.model)
        with self.assertRaises(AIError) as caught:
            make_client(Settings())
        self.assertEqual(caught.exception.code,'key_missing')
        with patch('openai.OpenAI',side_effect=ValueError(SECRET)):
            with self.assertRaises(AIError) as caught:
                make_client(Settings(api_key='mock'))
        self.assertEqual(caught.exception.code,'configuration')
        self.assertNotIn(SECRET,str(caught.exception))
        with patch('openai.OpenAI') as factory:
            make_client(Settings(api_key='mock'))
            self.assertEqual(factory.call_args.kwargs['timeout'],30.0)
            self.assertEqual(factory.call_args.kwargs['max_retries'],0)

    def test_structured_response_failures_are_distinct(self):
        cases=[
            (NS(status='incomplete',incomplete_details=NS(reason='max_output_tokens')),'output_limit'),
            (NS(status='incomplete',incomplete_details=None),'incomplete'),
            (NS(status='failed'),'service'),
            (NS(status='completed',output_text='',output=[NS(content=[NS(type='refusal')])]),'refused'),
            (NS(status='completed',output_text='not json',output=[]),'response_format'),
            (NS(status='completed',output_text='{"program":"invented"}',output=[]),'response_format'),
        ]
        for response,code in cases:
            with self.subTest(code=code):
                client=Mock();client.responses.create.return_value=response
                with self.assertRaises(AIError) as caught:
                    extract_conditions('질문',new_state(),load_activities(),Settings(),client=client)
                self.assertEqual(caught.exception.code,code)

    def test_valid_schema_and_verified_model_reasoning_options(self):
        Draft202012Validator.check_schema(SCHEMA)
        payload=empty_extraction();payload['conditions']['region']='강서구';payload['update_fields']=['region']
        Draft202012Validator(SCHEMA).validate(payload)
        for model,reasoning in [(Settings.model,{'effort':'none'}),('gpt-5-custom-unknown',None)]:
            client=Mock();client.responses.create.return_value=NS(status='completed',output_text=json.dumps(payload),output=[])
            self.assertEqual(extract_conditions('강서구',new_state(),load_activities(),Settings(model=model),client=client),payload)
            call=client.responses.create.call_args.kwargs
            self.assertEqual(call.get('reasoning'),reasoning)
            self.assertTrue(call['text']['format']['strict'])
            self.assertFalse(call['store'])
            self.assertEqual(call['max_output_tokens'],2000)

    def test_reported_question_falls_back_to_official_exercise_without_inventing_age(self):
        text='강서구에서 어르신이 참여할 수 있는 운동을 추천해줘'
        client=Mock();client.responses.create.side_effect=TimeoutError(SECRET)
        state=handle_turn(new_state(),text,load_activities(),Settings(api_key='mock'),client=client,as_of=DAY)
        self.assertEqual(state['conditions'],{'region':'강서구','category':'체육'})
        self.assertTrue(state['results'])
        self.assertTrue(all(x['category']=='체육' for x in state['results']))
        self.assertEqual(state['history'][-2]['content'],text)
        self.assertLessEqual(len(state['results']),3)

    def test_unrecognized_fallback_keeps_history_and_conditions_without_reusing_stale_cards(self):
        previous=handle_turn(new_state(),'강서구 국악',load_activities(),Settings(),as_of=DAY)
        before=deepcopy(previous)
        client=Mock();client.responses.create.side_effect=TimeoutError()
        state=handle_turn(previous,'새로운 취향을 알아주세요',load_activities(),Settings(api_key='mock'),client=client,as_of=DAY)
        self.assertEqual(previous,before)
        self.assertEqual(state['conditions'],before['conditions'])
        self.assertEqual(state['history'][:-2],before['history'])
        self.assertEqual(state['results'],[])
        self.assertEqual(state['code'],'clarify')

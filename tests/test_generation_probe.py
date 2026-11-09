"""Fixed-prompt generation diagnostics. All HTTP is MockTransport, never real Google."""
import json
import os
from types import SimpleNamespace as NS
from unittest import TestCase
from unittest.mock import Mock, patch
import httpx2
from google import genai
from google.genai import errors
from services.ai import empty_extraction, SCHEMA
from services.activities import load_activities
from services.config import Settings
from services.generation_probe import inspect_generation, PROBE_TEXT

SECRET='private-user-and-response-canary'


def completed(text):
    return NS(prompt_feedback=None,candidates=[NS(finish_reason='STOP')],text=text)


class GenerationProbeTest(TestCase):
    def test_simple_404_stops_without_structured_request_or_raw_error(self):
        client=Mock();client.models.generate_content.side_effect=errors.ClientError(404,{'error':{'message':SECRET}})
        result=inspect_generation(Settings(gemini_api_key='mock'),load_activities(),client=client)
        self.assertEqual(result['simple_code'],'generation_not_found')
        self.assertEqual(result['structured_code'],'not_run')
        self.assertEqual(result['comparison'],'simple_failed')
        client.models.generate_content.assert_called_once()
        self.assertNotIn(SECRET,json.dumps(result))

    def test_simple_success_structured_404_is_not_declared_schema_root_cause(self):
        client=Mock();client.models.generate_content.side_effect=[completed(SECRET),errors.ClientError(404,{'error':{'message':SECRET}})]
        result=inspect_generation(Settings(gemini_api_key='mock'),load_activities(),client=client)
        self.assertEqual(result['simple_code'],'ok')
        self.assertEqual(result['structured_code'],'generation_not_found')
        self.assertEqual(result['comparison'],'structured_failed')
        self.assertEqual(client.models.generate_content.call_count,2)
        self.assertNotIn(SECRET,json.dumps(result))
        calls=client.models.generate_content.call_args_list
        self.assertEqual(calls[0].kwargs['contents'],PROBE_TEXT)
        context=json.loads(calls[1].kwargs['contents'])
        self.assertEqual(context['current_utterance'],PROBE_TEXT)
        self.assertEqual(context['history'],[])
        self.assertEqual(context['current_conditions'],{})

    def test_both_success_has_no_generated_text_or_conditions_in_report(self):
        client=Mock();client.models.generate_content.side_effect=[completed(SECRET),completed(json.dumps(empty_extraction('other')))]
        result=inspect_generation(Settings(gemini_api_key='mock'),load_activities(),client=client)
        self.assertEqual(result['comparison'],'both_ok')
        self.assertEqual(result['free_tier'],'not_verified')
        self.assertNotIn('conditions',result)
        self.assertNotIn(SECRET,json.dumps(result))

    def test_response_validation_failure_and_truncation_are_not_404(self):
        for response,code in [(NS(prompt_feedback=None,candidates=[NS(finish_reason='MAX_TOKENS')]),'output_limit'),
                              (NS(prompt_feedback=NS(block_reason='SAFETY')),'refused'),
                              (completed(''),'response_format')]:
            client=Mock();client.models.generate_content.return_value=response
            result=inspect_generation(Settings(),load_activities(),client=client)
            self.assertEqual(result['simple_code'],code)
            self.assertEqual(result['structured_code'],'not_run')
        client=Mock();client.models.generate_content.side_effect=[completed('hello'),completed('not-json')]
        result=inspect_generation(Settings(),load_activities(),client=client)
        self.assertEqual(result['structured_code'],'response_format')

    def test_missing_key_and_invalid_model_do_not_create_client(self):
        with patch('google.genai.Client') as factory:
            result=inspect_generation(Settings(),load_activities())
            self.assertEqual(result['simple_code'],'key_missing')
            result=inspect_generation(Settings(gemini_api_key='mock',model='https://invalid/'+SECRET),load_activities())
            self.assertEqual(result['simple_code'],'model_config')
            self.assertIsNone(result['path'])
            factory.assert_not_called()
            self.assertNotIn(SECRET,json.dumps(result))

    def test_owned_client_closes_after_failure(self):
        client=Mock();client.models.generate_content.side_effect=TimeoutError(SECRET)
        with patch('services.generation_probe.make_client',return_value=client):
            result=inspect_generation(Settings(gemini_api_key='mock'),load_activities())
        self.assertEqual(result['simple_code'],'timeout')
        client.close.assert_called_once()
        self.assertNotIn(SECRET,json.dumps(result))

    def test_actual_sdk_same_post_path_and_precise_config_differences(self):
        calls=[]
        def handler(request):
            self.assertEqual(request.headers['x-goog-api-key'],'mock-only')
            calls.append((request.method,str(request.url),json.loads(request.content)))
            text=SECRET if len(calls)==1 else json.dumps(empty_extraction('other'))
            return httpx2.Response(200,json={'candidates':[{'content':{'parts':[{'text':text}]},'finishReason':'STOP'}]})
        original=genai.Client
        with httpx2.Client(transport=httpx2.MockTransport(handler)) as http:
            def factory(**kwargs):
                kwargs['http_options']=kwargs['http_options'].model_copy(update={'httpx_client':http})
                return original(**kwargs)
            with patch.dict(os.environ,{'GOOGLE_GENAI_API_VERSION':'v1','GOOGLE_GEMINI_BASE_URL':'https://wrong.invalid/v1beta'}), patch('google.genai.Client',side_effect=factory):
                result=inspect_generation(Settings(gemini_api_key='mock-only',model='models/gemini-2.5-flash'),load_activities())
        self.assertEqual(result['comparison'],'both_ok')
        self.assertEqual(len(calls),2)
        url='https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent'
        self.assertTrue(all(method=='POST' and path==url for method,path,body in calls))
        simple,structured=calls[0][2],calls[1][2]
        self.assertNotIn('systemInstruction',simple)
        self.assertNotIn('responseJsonSchema',simple['generationConfig'])
        self.assertNotIn('responseMimeType',simple['generationConfig'])
        self.assertIn('systemInstruction',structured)
        self.assertEqual(structured['generationConfig']['responseJsonSchema'],SCHEMA)
        self.assertEqual(structured['generationConfig']['responseMimeType'],'application/json')
        self.assertEqual(simple['generationConfig']['maxOutputTokens'],256)
        self.assertEqual(structured['generationConfig']['maxOutputTokens'],2000)
        self.assertNotIn(SECRET,json.dumps(result))

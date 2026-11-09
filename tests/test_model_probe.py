"""No real API key or internet: actual SDK with MockTransport and bounded metadata mocks."""
import json
import os
from dataclasses import replace
from types import SimpleNamespace as NS
from unittest import TestCase
from unittest.mock import Mock, patch
import httpx2
from google import genai
from google.genai import errors
from services.ai import AIError, empty_extraction, extract_conditions, make_client
from services.config import (Settings, load_settings, normalize_model, ModelSettingError,
                             GEMINI_API_BASE, GEMINI_API_VERSION)
from services.diagnostics import classify_error
from services.dialogue import handle_turn, new_state
from services.activities import load_activities
from services.model_probe import inspect_models

SECRET='private-provider-and-key-canary'

class ModelDiagnosticsTest(TestCase):
    def test_model_default_source_normalization_and_invalid_settings(self):
        with patch.dict(os.environ,{'GEMINI_MODEL':''}):
            self.assertEqual(load_settings().model,'gemini-2.5-flash')
            self.assertEqual(load_settings({'GEMINI_MODEL':'  '}).model_source,'default')
            settings=load_settings({'GEMINI_MODEL':' models/gemini-2.5-flash '})
            self.assertEqual(settings.model_source,'secrets')
            self.assertEqual(normalize_model(settings.model),'gemini-2.5-flash')
            with self.assertRaises(ModelSettingError):normalize_model(load_settings({'GEMINI_MODEL':123}).model)
        with patch.dict(os.environ,{'GEMINI_MODEL':'gemini-typo-but-valid-format'}):
            settings=load_settings({'GEMINI_MODEL':'gemini-2.5-flash'})
            self.assertEqual(settings.model_source,'environment')
            self.assertEqual(settings.model,'gemini-typo-but-valid-format')
        for value in ('models/models/gemini-2.5-flash','https://example.invalid/'+SECRET,SECRET,'"gemini-2.5-flash"'):
            with self.subTest(value=value),self.assertRaises(AIError) as caught:
                extract_conditions('강서구 운동',new_state(),load_activities(),Settings(gemini_api_key='mock',model=value))
            self.assertEqual(caught.exception.code,'model_config')
            self.assertNotIn(SECRET,str(caught.exception))
            self.assertNotIn(value,repr(Settings(model=value)))

    def test_real_sdk_uses_exact_official_generation_url_ignoring_environment_override(self):
        calls=[]
        payload=empty_extraction()
        def handler(request):
            calls.append((request.method,str(request.url)))
            self.assertEqual(request.headers['x-goog-api-key'],'mock-only')
            return httpx2.Response(200,json={'candidates':[{'content':{'parts':[{'text':json.dumps(payload)}]},'finishReason':'STOP'}]})
        original=genai.Client
        with httpx2.Client(transport=httpx2.MockTransport(handler)) as http:
            def client_factory(**kwargs):
                self.assertEqual(kwargs['http_options'].base_url,GEMINI_API_BASE)
                kwargs['http_options']=kwargs['http_options'].model_copy(update={'httpx_client':http})
                return original(**kwargs)
            with patch.dict(os.environ,{'GOOGLE_GEMINI_BASE_URL':'https://wrong.invalid/v1beta/'+SECRET}),patch('google.genai.Client',side_effect=client_factory):
                result=extract_conditions('강서구',new_state(),load_activities(),Settings(gemini_api_key='mock-only',model='models/gemini-2.5-flash'))
        self.assertEqual(result,payload)
        self.assertEqual(calls,[('POST','https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent')])

    def test_404_context_is_distinct_from_permission_and_non_json_route_response(self):
        error=errors.ClientError(404,{'error':{'message':SECRET,'status':'NOT_FOUND'}})
        for operation,code in [('generate','generation_not_found'),('model_get','model_metadata_not_found'),('model_list','model_list_not_found')]:
            self.assertEqual(classify_error(error,operation=operation),code)
        html=httpx2.Response(404,headers={'content-type':'text/html'},text=SECRET)
        self.assertEqual(classify_error(errors.ClientError(404,{},response=html)),'non_json_not_found')
        self.assertEqual(classify_error(errors.ClientError(403,{})),'permission')

    def test_metadata_success_does_not_assert_generation_or_free_tier(self):
        client=Mock()
        client.models.get.return_value=NS(supported_actions=['generateContent'])
        client.models.list.return_value=NS(page=[NS(name='models/gemini-2.5-flash',supported_actions=['generateContent']),
            NS(name=SECRET,supported_actions=['generateContent']),NS(name='models/gemini-private-method',supported_actions=['embedContent'])])
        result=inspect_models(Settings(gemini_api_key='mock'),client=client)
        self.assertEqual(result['metadata_code'],'metadata_ok')
        self.assertEqual(result['models'],['gemini-2.5-flash'])
        self.assertEqual(result['generation'],'not_tested')
        self.assertEqual(result['free_tier'],'not_verified')
        client.models.generate_content.assert_not_called()
        self.assertNotIn(SECRET,json.dumps(result))
        client.models.list.assert_called_once_with(config={'page_size':50})

    def test_metadata_and_list_404_are_reported_separately_and_key_missing_has_no_request(self):
        client=Mock()
        client.models.get.side_effect=errors.ClientError(404,{'error':{'message':SECRET}})
        client.models.list.side_effect=errors.ClientError(404,{'error':{'message':SECRET}})
        result=inspect_models(Settings(gemini_api_key='mock'),client=client)
        self.assertEqual(result['metadata_code'],'model_metadata_not_found')
        self.assertEqual(result['list_code'],'model_list_not_found')
        self.assertNotIn(SECRET,json.dumps(result))
        with patch('google.genai.Client') as factory:
            result=inspect_models(Settings())
            factory.assert_not_called()
        self.assertEqual(result['list_code'],'key_missing')

    def test_invalid_model_can_still_list_metadata_and_owned_client_is_closed(self):
        client=Mock();client.models.list.return_value=NS(page=[])
        with patch('services.model_probe.make_client',return_value=client):
            result=inspect_models(Settings(gemini_api_key='mock',model=SECRET))
        self.assertIsNone(result['model'])
        self.assertEqual(result['model_setting'],'model_config')
        client.models.get.assert_not_called()
        client.close.assert_called_once()
        self.assertEqual(result['list_code'],'list_ok')
        self.assertNotIn(SECRET,json.dumps(result))

    def test_real_sdk_metadata_paths_and_methods_are_read_only(self):
        paths=[]
        def handler(request):
            paths.append((request.method,request.url.path))
            if request.url.path.endswith('/models/gemini-2.5-flash'):
                return httpx2.Response(200,json={'name':'models/gemini-2.5-flash','supportedGenerationMethods':['generateContent']})
            return httpx2.Response(200,json={'models':[{'name':'models/gemini-2.5-flash','supportedGenerationMethods':['generateContent']}]})
        with httpx2.Client(transport=httpx2.MockTransport(handler)) as http:
            with genai.Client(api_key='mock',vertexai=False,enterprise=False,http_options={'base_url':GEMINI_API_BASE,'api_version':GEMINI_API_VERSION,'httpx_client':http}) as client:
                result=inspect_models(Settings(gemini_api_key='mock'),client=client)
        self.assertTrue(result['generate_content_supported'])
        self.assertEqual(result['models'],['gemini-2.5-flash'])
        self.assertEqual(paths,[('GET','/v1beta/models/gemini-2.5-flash'),('GET','/v1beta/models')])

    def test_404_fallback_preserves_official_results_and_question(self):
        client=Mock();client.models.generate_content.side_effect=errors.ClientError(404,{'error':{'message':SECRET}})
        state=handle_turn(new_state(),'강서구 운동',load_activities(),Settings(gemini_api_key='mock'),client=client)
        self.assertEqual(state['diagnostic']['code'],'generation_not_found')
        self.assertTrue(state['results'])
        self.assertEqual(state['history'][-2]['content'],'강서구 운동')
        self.assertNotIn(SECRET,json.dumps(state))

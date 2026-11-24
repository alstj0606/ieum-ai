"""Actual Google SDK + in-memory HTTP transport. No live Google requests."""
import json,os
from unittest import TestCase
from unittest.mock import patch
import httpx2
from google import genai
from services.ai import empty_extraction
from services.config import Settings,load_settings
from services.conversation_probe import inspect_conversation,PROMPTS
from services.gemini_trace import ACTIVE_TRACE

SECRET='synthetic-provider-private-value'

def plan(reply='종이와 펜으로 그림부터 시작해 보세요.',route='howto'):
 return dict(extraction=empty_extraction('other'),route=route,reply=reply,idea_ids=[],hobbies=[])

def response(text):return {'candidates':[{'content':{'parts':[{'text':text}]},'finishReason':'STOP'}]}

class ConversationProbeTest(TestCase):
 def invoke(self,handler):
  calls=[];clients=[];original=genai.Client
  def transport(request):
   calls.append((request.url.path,json.loads(request.content)))
   self.assertEqual(request.headers['x-goog-api-key'],SECRET)
   return handler(request,len(calls))
  def factory(**kwargs):
   options=kwargs['http_options']
   http=httpx2.Client(transport=httpx2.MockTransport(transport),event_hooks=options.client_args['event_hooks'])
   clients.append(http);kwargs['http_options']=options.model_copy(update={'httpx_client':http})
   return original(**kwargs)
  try:
   with patch('google.genai.Client',side_effect=factory):out=inspect_conversation(Settings(gemini_api_key=SECRET))
  finally:
   for http in clients:http.close()
  self.assertIsNone(ACTIVE_TRACE.get());self.assertNotIn(SECRET,json.dumps(out));return out,calls
 def test_sdk_http_path_schema_context_and_actual_reply_use(self):
  def handler(request,n):
   text=json.dumps(plan('혼자 즐길 취미를 함께 생각해 봐요. 어떤 도구가 있나요?' if n==1 else '종이와 펜으로 그림부터 시작해 보세요.','explore' if n==1 else 'howto'),ensure_ascii=False)
   return httpx2.Response(200,json=response(text))
  out,calls=self.invoke(handler)
  self.assertTrue(out['conversation_success']);self.assertTrue(out['generation_success']);self.assertEqual(out['http_status'],200);self.assertTrue(out['context_forwarded'])
  self.assertEqual(len(calls),2)
  for path,body in calls:
   self.assertEqual(path,'/v1beta/models/gemini-2.5-flash:generateContent')
   self.assertEqual(body['generationConfig']['responseMimeType'],'application/json')
   self.assertIn('hobbies',body['generationConfig']['responseJsonSchema']['properties'])
  context=json.loads(calls[1][1]['contents'][0]['parts'][0]['text'])
  self.assertEqual(context['utterance'],PROMPTS[1]);self.assertEqual(context['conversation'][0]['content'],PROMPTS[0])
  self.assertIn('혼자 즐길 취미',context['conversation'][1]['content'])
  self.assertTrue(all(x['http_request_attempted'] and x['http_response_received'] and x['reply_used'] for x in out['turns']))
 def test_http_error_status_is_not_lost_through_fallback(self):
  for status,code in ((401,'authentication'),(403,'permission'),(404,'generation_not_found'),(429,'rate_limit'),(503,'service')):
   out,calls=self.invoke(lambda r,n:httpx2.Response(status,json={'error':{'code':status,'message':SECRET}}))
   self.assertEqual(out['http_status'],status);self.assertEqual(out['error_type'],code);self.assertFalse(out['conversation_success']);self.assertFalse(out['generation_success']);self.assertEqual(len(calls),1)
 def test_timeout_is_distinct_from_http_response(self):
  def timeout(r,n):raise httpx2.ReadTimeout(SECRET)
  out,calls=self.invoke(timeout);self.assertEqual(out['error_type'],'timeout');self.assertIsNone(out['http_status']);self.assertTrue(out['http_request_attempted']);self.assertFalse(out['http_response_received'])
 def test_200_parse_validation_and_policy_rejection_are_not_network_failures(self):
  for text,stage,code in (('not json','parse','response_format'),('{}','validation','response_format'),(json.dumps(plan('어느 동네에서 찾아볼까요?','search')),None,'reply_not_used')):
   out,calls=self.invoke(lambda r,n:httpx2.Response(200,json=response(text)))
   self.assertEqual(out['http_status'],200);self.assertEqual(out['error_type'],code);self.assertEqual(out['turns'][0]['stage'],stage);self.assertFalse(out['conversation_success']);self.assertTrue(out['generation_success'])
 def test_no_key_and_invalid_model_never_make_requests(self):
  with patch('google.genai.Client') as client:
   self.assertEqual(inspect_conversation(Settings())['error_type'],'key_missing')
   out=inspect_conversation(Settings(gemini_api_key=SECRET,model=SECRET));self.assertEqual(out['error_type'],'model_config');self.assertNotIn(SECRET,json.dumps(out));client.assert_not_called()
 def test_settings_provenance_and_environment_conflict_are_safe(self):
  with patch.dict(os.environ,{'GEMINI_API_KEY':'environment-private','GEMINI_MODEL':'gemini-2.5-flash'}):
   s=load_settings({'GEMINI_API_KEY':'secrets-private','GEMINI_MODEL':'gemini-other'})
   self.assertEqual(s.gemini_api_key,'environment-private');self.assertTrue(s.gemini_key_conflict);self.assertTrue(s.model_setting_conflict);self.assertEqual(s.gemini_key_source,'environment')
   self.assertNotIn('environment-private',repr(s));self.assertNotIn('secrets-private',repr(s))
   same=load_settings({'GEMINI_API_KEY':'environment-private'});self.assertEqual(same.gemini_key_source,'environment_and_secrets');self.assertFalse(same.gemini_key_conflict)

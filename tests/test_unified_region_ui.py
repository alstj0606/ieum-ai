"""All region UI entrypoints use the same touch dialog, including old sessions."""
from pathlib import Path
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from services.config import Settings
from services.dialogue import new_state
from services.regions import selection

ROOT=Path(__file__).resolve().parents[1]
class UnifiedRegionUITest(TestCase):
 def app(self,name='app.py'):
  app=AppTest.from_file(str(ROOT/name)).run();self.assertFalse(app.exception);return app
 def choose(self,app,label):
  next(b for b in app.button if b.label==label+' →').click().run();self.assertFalse(app.exception)
 def assert_picker(self,app):
  self.assertFalse(app.exception)
  self.assertEqual(len([b for b in app.button if b.key and b.key.startswith('region_option_province_')]),17)
  self.assertFalse([s for s in app.selectbox if s.label in ('시·도','시·군·구','읍·면·동')])
 def test_restored_region_drafts_never_render_legacy_choices(self):
  with patch('services.config.load_settings',return_value=Settings()):
   for stage in ('region_city','region_district','region_dong'):
    app=self.app();s=new_state();s.update(code='question',pending='region',search_requested=True,picker={'stage':stage,'city':'서울','district':'강서구'})
    app.session_state['dialog']=deepcopy(s);app.session_state['turns']=[{'user':'이전 지역 선택','state':s,'turn_id':1}];app.session_state['turn_seq']=1;app.run()
    self.assertFalse([b for b in app.button if b.key and b.key.startswith(('city_','district_','dong_'))])
    app.button(key='choose_region').click().run();self.assert_picker(app)
    app.session_state['region_draft']={'stage':'legacy_selectbox'};app.run();self.assert_picker(app)
 def test_manual_and_legacy_entry_share_touch_confirmation(self):
  with patch('services.config.load_settings',return_value=Settings()):
   for entry in ('app.py','gangseo_app.py'):
    app=self.app(entry);app.button(key='manual_region_picker').click().run();self.assert_picker(app)
    self.choose(app,'강원특별자치도');self.choose(app,'강릉시');self.choose(app,'강남동')
    app.button(key='region_confirm').click().run();self.assertFalse(app.exception);self.assertFalse(app.session_state['region_open'])
    state=app.session_state['dialog'];self.assertEqual(state['location']['code'],selection('강원특별자치도','강릉시','강남동')['code']);self.assertIsNone(state['pending'])
 def test_ambiguous_candidate_opens_the_same_final_confirmation(self):
  with patch('services.config.load_settings',return_value=Settings()):
   app=self.app();s=dict(new_state(),life_mode=True,code='conversation',pending='location_confirmation',conversation_route='search',search_requested=True,location_candidates=[selection('강원특별자치도','강릉시','강남동')])
   s['conditions']={'activity_type':'수영','budget_amount':0};app.session_state['turns']=[{'user':'동네 확인','state':s,'turn_id':1}];app.session_state['dialog']=deepcopy(s);app.session_state['turn_seq']=1;app.run()
   app.button(key='location_candidate_0').click().run();self.assertFalse(app.exception);self.assertTrue(app.session_state['region_open']);self.assertEqual(app.session_state['region_draft']['stage'],'confirm')
   app.button(key='region_confirm').click().run();self.assertFalse(app.exception);self.assertFalse(app.session_state['region_open']);self.assertEqual(app.session_state['dialog']['conditions']['budget_amount'],0)

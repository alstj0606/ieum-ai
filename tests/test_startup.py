"""Fresh-process import/startup regressions; no provider requests or credentials."""
import os
from pathlib import Path
import subprocess
import sys
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[1]


class StartupTest(TestCase):
    def run_fresh(self, script):
        env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1')
        for key in ('GEMINI_API_KEY', 'GOOGLE_API_KEY', 'OPENAI_API_KEY'):
            env.pop(key, None)
        result = subprocess.run([sys.executable, '-c', script], cwd=ROOT,
                                env=env, capture_output=True, text=True, timeout=45)
        # Do not dump captured provider/runtime bodies into CI logs on failure.
        self.assertEqual(result.returncode, 0, 'Fresh-process startup/import check failed')
        return result.stdout

    def test_every_app_service_import_exists_and_called_imports_are_callable(self):
        output = self.run_fresh('''
import ast
import importlib
from pathlib import Path
root=Path.cwd().resolve()
tree=ast.parse((root/'app.py').read_text())
called={n.func.id for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
count=0
for node in ast.walk(tree):
    if not isinstance(node,ast.ImportFrom) or not (node.module or '').startswith('services.'):
        continue
    module=importlib.import_module(node.module)
    assert root in Path(module.__file__).resolve().parents
    for name in node.names:
        value=getattr(module,name.name)
        if (name.asname or name.name) in called:
            assert callable(value)
        count+=1
from services.dialogue import choose_alternative
assert callable(choose_alternative)
print('service_imports_ok',count)
''')
        self.assertIn('service_imports_ok', output)

    def test_fresh_streamlit_app_executes_with_no_api_keys(self):
        output = self.run_fresh('''
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from services.config import Settings
with patch('services.config.load_settings', return_value=Settings()):
    app=AppTest.from_file('app.py',default_timeout=20).run()
    assert not app.exception
    assert len(app.chat_input)==1
    assert app.session_state['dialog']['code']=='start'
    assert any(title.value=='이음 AI' for title in app.title)
print('app_startup_ok')
''')
        self.assertIn('app_startup_ok', output)

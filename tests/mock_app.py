"""Local-only browser fixture. Never deploy this entrypoint; never use real keys."""
from pathlib import Path
import runpy
from unittest.mock import patch
from google import genai

original_client = genai.Client


def local_client(*args, **kwargs):
    # Production pins Google's host. Only this test harness redirects fake credentials.
    options = kwargs['http_options'].model_copy(update={'base_url':'http://127.0.0.1:18503'})
    kwargs['http_options'] = options
    return original_client(*args, **kwargs)


with patch('google.genai.Client',side_effect=local_client):
    runpy.run_path(str(Path(__file__).resolve().parents[1]/'gangseo_app.py'),run_name='__main__')

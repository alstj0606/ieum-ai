"""Local fault injection only: run the real app with a failing diagnostic."""
from pathlib import Path
import runpy
import services.config as config
import services.runtime_diagnostics as diagnostics
from services.config import Settings

config.load_settings=lambda *args,**kwargs:Settings()
def fail(*args,**kwargs):raise TypeError('synthetic-private-value-not-for-logs')
diagnostics.snapshot=fail
runpy.run_path(str(Path(__file__).resolve().parents[1]/'app.py'),run_name='__main__')

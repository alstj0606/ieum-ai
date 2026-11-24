"""Per-turn transport evidence. Never retain request or response content."""
from contextvars import ContextVar

ACTIVE_TRACE=ContextVar("ieum_gemini_http_trace",default=None)


class HTTPTrace:
    """Observe transport events only. Never read/store URLs, headers or bodies."""
    def __init__(self):
        self.http_request_attempted=False;self.http_response_received=False
        self.http_status=None;self.generation_succeeded=False;self.json_parsed=False;self.validated=False
    def request(self,request):self.http_request_attempted=True
    def response(self,response):
        self.http_response_received=True
        status=getattr(response,'status_code',None)
        if type(status) is int and 100<=status<=599:self.http_status=status
    def public(self):
        return {key:getattr(self,key) for key in ('http_request_attempted','http_response_received','http_status','generation_succeeded','json_parsed','validated')}


def error_http_status(error):
    from google.genai.errors import APIError
    if isinstance(error,APIError):
        code=error.code
        if type(code) is int and 100<=code<=599:return code
    return None

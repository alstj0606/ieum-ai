"""로컬 SDK/브라우저 통합 테스트용 모의 API. 실제 AI/STT/TTS가 아니다.

저장소 루트에서 python -m tests.mock_voice_server 대신
PYTHONPATH=. python tests/mock_voice_server.py 로 실행한다. localhost만 수신한다.
요청 본문·인증 헤더를 기록하지 않는다. 외부 API 호출은 하지 않는다.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import math
import struct
import wave

from services.dialogue import basic_extract


def tone():
    stream = BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(16000)
        audio.writeframes(b"".join(struct.pack("<h", int(3000 * math.sin(i * 0.17))) for i in range(8000)))
    return stream.getvalue()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.split('?')[0] == '/v1beta/models':
            data={'models':[{'name':'models/gemini-2.5-flash','supportedGenerationMethods':['generateContent']}]}
        elif self.path == '/v1beta/models/gemini-2.5-flash':
            data={'name':'models/gemini-2.5-flash','supportedGenerationMethods':['generateContent']}
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        content_type = "application/json"
        if self.path == "/v1beta/models/gemini-2.5-flash:generateContent":
            context = json.loads(json.loads(body)["contents"][0]["parts"][0]["text"])
            # Deliberate free-quota simulation, not a diagnosis of a real Google project.
            if context["current_utterance"] == "강서구에서 어르신이 참여할 수 있는 운동을 추천해줘":
                self.send_response(429)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error":{"code":429,"status":"RESOURCE_EXHAUSTED",
                    "message":"provider-private-canary-no-log"}}).encode())
                return
            if context["current_utterance"] == "강서구 운동을 추천해줘":
                self.send_response(404)
                self.send_header('Content-Type','application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error':{'code':404,'status':'NOT_FOUND','message':'private-provider-canary'}}).encode())
                return
            request = basic_extract(context["current_utterance"], {
                "pending": context["pending"], "conditions": context["current_conditions"],
            })
            data = {"candidates":[{"content":{"parts":[{"text":json.dumps(request,ensure_ascii=False)}],
                    "role":"model"}, "finishReason":"STOP", "index":0}]}
        elif self.path == "/v1/audio/transcriptions":
            data = {"text": "강서구에서 국악 공연을 보고 싶어요"}
        elif self.path == "/v1/audio/speech":
            # 모의 음성은 말소리가 아닌 시험용 톤이다. 브라우저 재생만 검사한다.
            content_type = "audio/wav"
            data = tone()
        else:
            self.send_error(404)
            return
        encoded = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


if __name__ == "__main__":
    print("Mock API only: http://127.0.0.1:18503/v1 (no real AI calls)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 18503), Handler).serve_forever()

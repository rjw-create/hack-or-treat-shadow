"""Model-client error paths and warm-up, against a fake Ollama server (no real model needed)."""
import http.server
import json
import os
import socket
import threading
import unittest
from unittest import mock

from shadow import llm

PULLED = ["gemma4:e4b", "other:latest"]


class FakeOllama(http.server.BaseHTTPRequestHandler):
    requests = []  # (path, body) of every POST, shared by the class

    def log_message(self, *args):
        pass

    def reply(self, code, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/tags":
            self.reply(200, {"models": [{"name": n} for n in PULLED]})
        else:
            self.reply(404, {"error": "not found"})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOllama.requests.append((self.path, body))
        if body.get("model") not in PULLED:
            self.reply(404, {"error": f"model '{body.get('model')}' not found"})
        elif self.path == "/api/chat":
            self.reply(200, {"message": {"content": '{"ok": true, "reason": "fake"}'}})
        else:
            self.reply(200, {"done": True})


def env(host, planner="gemma4:e4b", checker="gemma4:e4b"):
    values = {"OLLAMA_HOST": host}
    if planner:
        values["SHADOW_PLANNER_MODEL"] = planner
    if checker:
        values["SHADOW_CHECKER_MODEL"] = checker
    return mock.patch.dict("os.environ", values)


class LLMClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeOllama)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.host = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        FakeOllama.requests.clear()

    def test_preflight_passes_when_models_are_pulled(self):
        with env(self.host, planner="other"):  # "other" is listed as other:latest
            self.assertEqual(llm.preflight(["planner", "checker"]), {"planner": "other", "checker": "gemma4:e4b"})

    def test_preflight_names_missing_model_and_pull_command(self):
        with env(self.host, checker="gemma4:26b"), self.assertRaises(llm.LLMError) as ctx:
            llm.preflight(["planner", "checker"])
        self.assertIn("ollama pull gemma4:26b", str(ctx.exception))

    def test_preflight_names_unset_variable(self):
        with env(self.host, checker=None), self.assertRaises(llm.LLMError) as ctx:
            os.environ.pop("SHADOW_CHECKER_MODEL", None)  # patch.dict restores it afterwards
            llm.preflight(["planner", "checker"])
        self.assertIn("SHADOW_CHECKER_MODEL", str(ctx.exception))

    def test_unreachable_server_says_how_to_start_it(self):
        with socket.socket() as s:  # grab a free port, then close it so nothing is listening
            s.bind(("127.0.0.1", 0))
            dead = f"http://127.0.0.1:{s.getsockname()[1]}"
        with env(dead), self.assertRaises(llm.LLMError) as ctx:
            llm.preflight(["checker"])
        self.assertIn("Could not reach Ollama", str(ctx.exception))
        self.assertIn("ollama serve", str(ctx.exception))

    def test_http_error_reports_server_message_not_unreachable(self):
        with env(self.host, checker="missing:tag"), self.assertRaises(llm.LLMError) as ctx:
            llm.chat_json("checker", "hi")
        self.assertIn("HTTP 404", str(ctx.exception))
        self.assertIn("model 'missing:tag' not found", str(ctx.exception))
        self.assertNotIn("Could not reach", str(ctx.exception))

    def test_warmup_loads_each_model_once_with_keep_alive(self):
        with env(self.host):
            self.assertEqual(llm.warmup(["planner", "checker"]), ["gemma4:e4b"])
        self.assertEqual(FakeOllama.requests,
                         [("/api/generate", {"model": "gemma4:e4b", "prompt": "", "keep_alive": llm.KEEP_ALIVE})])

    def test_chat_sends_keep_alive_and_think(self):
        with env(self.host):
            self.assertEqual(llm.chat_json("checker", "hi", think=False), {"ok": True, "reason": "fake"})
        path, body = FakeOllama.requests[-1]
        self.assertEqual(path, "/api/chat")
        self.assertEqual(body["keep_alive"], llm.KEEP_ALIVE)
        self.assertIs(body["think"], False)


if __name__ == "__main__":
    unittest.main()

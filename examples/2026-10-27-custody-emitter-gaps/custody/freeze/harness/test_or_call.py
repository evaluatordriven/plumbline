#!/usr/bin/env python3
# STATUS: FROZEN-BUILD 2026-10-27T21:53:35Z — offline tests for or_call.py (no network; a fake transport serves recorded fixtures).
"""Run:  PLUMBLINE=<plumbline checkout at ff350e3> python3 -m unittest test_or_call -v"""
import json, os, sys, tempfile, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import or_call  # noqa: E402

FX = HERE / "fixtures"
FAKE_KEY = "sk-or-v1-FAKEKEYFORTESTS0123456789abcdef"


def fx(name):
    return json.loads((FX / name).read_text())


class Fake:
    """Serves chat + generation fixtures and records what was sent."""
    def __init__(self, chat, gens):
        self.chat, self.gens, self.sent = chat, list(gens), []

    def request(self, method, url, headers, body, timeout=300):
        self.sent.append({"method": method, "url": url, "headers": headers, "body": json.loads(body) if body else None})
        if method == "POST":
            return self.chat["status"], self.chat["headers"], json.dumps(self.chat["body"]).encode()
        g = self.gens.pop(0) if self.gens else (404, {"error": "not found"})
        return g[0], {}, json.dumps(g[1]).encode()


class OrCallTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.key = self.d / "key"
        self.key.write_text(FAKE_KEY + "\n")
        os.chmod(self.key, 0o600)
        self.msgs = self.d / "m.json"
        self.msgs.write_text(json.dumps([{"role": "user", "content": "hi"}]))
        self.log = self.d / "custody" / "evidence" / "harness-maker-deepseek.log"
        self.out = self.d / "reply.txt"

    def args(self, *extra):
        return or_call.parser().parse_args(
            ["--key-file", str(self.key), "--seat", "maker", "--log", str(self.log), "--model",
             "deepseek/deepseek-v4.1-flash-1017", "--tag", "deepinfra/fp8", "--pin-provider", "DeepInfra",
             "--messages", str(self.msgs), "--out", str(self.out), "--gen-wait", "0", *extra])

    def run_ok(self, *extra):
        f = Fake(fx("chat-deepinfra.json"), [(200, fx("generation-deepinfra.json"))])
        return or_call.call(self.args(*extra), f, sleep=lambda s: None), f

    def test_request_shape_provider_block_and_header(self):
        rc, f = self.run_ok()
        self.assertEqual(rc, 0)
        post = f.sent[0]
        self.assertEqual(post["url"], "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(post["body"]["provider"], {"order": ["deepinfra/fp8"], "allow_fallbacks": False, "zdr": True})
        self.assertEqual(post["headers"]["X-OpenRouter-Metadata"], "enabled")
        self.assertEqual(f.sent[1]["method"], "GET")
        self.assertIn("/generation?id=gen-", f.sent[1]["url"])

    def test_authorization_redacted_and_key_absent(self):
        self.run_ok()
        text = self.log.read_text()
        self.assertNotIn(FAKE_KEY, text)
        e = json.loads(text)[0]
        self.assertEqual(e["request"]["headers"]["Authorization"], "Bearer [REDACTED]")

    def test_logs_raw_response_headers_and_generation_with_timestamps(self):
        self.run_ok()
        e = json.loads(self.log.read_text())[0]
        self.assertEqual(e["response_headers"]["Date"], "Tue, 27 Oct 2026 18:23:32 GMT")
        self.assertEqual(e["response"], fx("chat-deepinfra.json")["body"])
        self.assertEqual(e["generation"], fx("generation-deepinfra.json"))
        for k in ("sent_at", "received_at", "generation_fetched_at"):
            self.assertRegex(e[k], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d+Z$")
        self.assertTrue(e["verdict"]["ok"])
        self.assertEqual(self.out.read_text(), fx("chat-deepinfra.json")["body"]["choices"][0]["message"]["content"])

    def test_refuses_when_served_by_another_provider(self):
        f = Fake(fx("chat-novita.json"), [(200, fx("generation-novita.json"))])
        rc = or_call.call(self.args(), f, sleep=lambda s: None)
        self.assertEqual(rc, 4)
        self.assertFalse(self.out.exists())
        e = json.loads(self.log.read_text())[0]
        self.assertFalse(e["verdict"]["ok"])
        self.assertIn("Novita", e["verdict"]["refusal"])

    def test_refuses_when_nothing_says_who_served(self):
        chat = fx("chat-deepinfra.json")
        chat["body"].pop("provider"); chat["body"].pop("openrouter_metadata")
        f = Fake(chat, [])
        rc = or_call.call(self.args("--gen-tries", "2"), f, sleep=lambda s: None)
        self.assertEqual(rc, 4)
        self.assertFalse(self.out.exists())

    def test_generation_missing_is_logged_null_exit5(self):
        f = Fake(fx("chat-deepinfra.json"), [(404, {"error": "x"}), (404, {"error": "x"})])
        rc = or_call.call(self.args("--gen-tries", "2"), f, sleep=lambda s: None)
        self.assertEqual(rc, 5)
        e = json.loads(self.log.read_text())[0]
        self.assertIsNone(e["generation"])
        self.assertFalse(e["verdict"]["generation_reply"])

    def test_generation_retried_until_ready(self):
        f = Fake(fx("chat-deepinfra.json"), [(404, {}), (200, fx("generation-deepinfra.json"))])
        self.assertEqual(or_call.call(self.args("--gen-tries", "3"), f, sleep=lambda s: None), 0)
        self.assertIsNotNone(json.loads(self.log.read_text())[0]["generation"])

    def test_appends_per_seat_log_and_names(self):
        self.run_ok("--call", "maker_call_1")
        self.run_ok("--call", "maker_call_2")
        items = json.loads(self.log.read_text())
        self.assertEqual([i["call"] for i in items], ["maker_call_1", "maker_call_2"])
        bad = or_call.parser().parse_args(["--key-file", str(self.key), "--seat", "maker", "--log",
                                           str(self.d / "harness-eval-glm.log"), "--model", "m", "--tag", "deepinfra/fp8",
                                           "--pin-provider", "DeepInfra", "--messages", str(self.msgs)])
        self.assertEqual(or_call.call(bad, Fake(fx("chat-deepinfra.json"), [])), 2)

    def test_key_file_permissions_enforced(self):
        os.chmod(self.key, 0o644)
        with self.assertRaises(SystemExit):
            or_call.call(self.args(), Fake(fx("chat-deepinfra.json"), []))

    def test_ledger_pin(self):
        led = self.d / "custody-events.jsonl"
        led.write_text(json.dumps({"event": "pin", "seat": "maker", "via": "openrouter.ai", "provider": "DeepInfra",
                                   "slug": "deepinfra/fp8", "host": "api.deepinfra.com", "at": "2026-10-27T18:23:27Z"}) + "\n")
        a = or_call.parser().parse_args(["--key-file", str(self.key), "--seat", "maker", "--log", str(self.log),
                                         "--model", "deepseek/deepseek-v4.1-flash-1017", "--ledger", str(led),
                                         "--messages", str(self.msgs), "--gen-wait", "0"])
        f = Fake(fx("chat-deepinfra.json"), [(200, fx("generation-deepinfra.json"))])
        self.assertEqual(or_call.call(a, f, sleep=lambda s: None), 0)
        self.assertEqual(f.sent[0]["body"]["provider"]["order"], ["deepinfra/fp8"])

    @unittest.skipUnless(os.environ.get("PLUMBLINE"), "set PLUMBLINE to a plumbline checkout (main ff350e3)")
    def test_log_reads_in_emitter_parser_with_pin(self):
        sys.path.insert(0, str(Path(os.environ["PLUMBLINE"]) / "kit"))
        import custody_history as H
        self.run_ok("--call", "maker_call_1")
        ref = H.Refusals()
        calls = H.read_log(self.log, ref, "maker")
        self.assertEqual(len(calls), 1)
        self.assertFalse(ref, getattr(ref, "items", ref))
        pin = {"via": "openrouter.ai", "provider": "DeepInfra", "slug": "deepinfra/fp8", "host": "api.deepinfra.com",
               "declaredAt": "2026-10-27T18:23:27Z"}
        host, route = H.endpoint_of(calls[0], ref, "maker", pin)
        self.assertEqual(host, "api.deepinfra.com")
        self.assertEqual(H.routing_request(calls[0].raw), {"order": ["deepinfra/fp8"], "allow_fallbacks": False, "zdr": True})
        self.assertEqual(H.iso(calls[0].at), "2026-10-27T18:23:32Z")


if __name__ == "__main__":
    unittest.main()

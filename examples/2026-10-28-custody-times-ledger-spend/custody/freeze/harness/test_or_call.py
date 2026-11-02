#!/usr/bin/env python3
# STATUS: FROZEN-BUILD 2026-10-28T20:36:28Z — offline tests for or_call.py incl. the spend guard (no network; a fake transport serves recorded fixtures).
"""Run:  TMPDIR=<job tmp> PLUMBLINE=<plumbline checkout at b6ff8b5> python3 -m unittest test_or_call -v"""
import json, os, sys, tempfile, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import or_call  # noqa: E402

FX = HERE / "fixtures"
FAKE_KEY = "sk-or-v1-FAKEKEYFORTESTS0123456789abcdef"


def fx(name):
    return json.loads((FX / name).read_text())


class Fake:
    """Serves chat + generation fixtures and records what was sent."""
    def __init__(self, chat, gens, usage=10.0):
        self.chat, self.gens, self.sent, self.usage = chat, list(gens), [], usage

    def request(self, method, url, headers, body, timeout=300):
        self.sent.append({"method": method, "url": url, "headers": headers, "body": json.loads(body) if body else None})
        if method == "GET" and url.endswith("/key"):
            if self.usage is None:
                return 401, {}, b'{"error":"x"}'
            return 200, {}, json.dumps({"data": {"limit": None, "usage": self.usage}}).encode()
        if method == "POST":
            return self.chat["status"], self.chat["headers"], json.dumps(self.chat["body"]).encode()
        g = self.gens.pop(0) if self.gens else (404, {"error": "not found"})
        return g[0], {}, json.dumps(g[1]).encode()


class OrCallTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(dir=os.environ.get("TMPDIR")))
        self.key = self.d / "key"
        self.key.write_text(FAKE_KEY + "\n")
        os.chmod(self.key, 0o600)
        self.msgs = self.d / "m.json"
        self.msgs.write_text(json.dumps([{"role": "user", "content": "hi"}]))
        self.log = self.d / "custody" / "evidence" / "harness-maker-deepseek.log"
        self.out = self.d / "reply.txt"
        self.spend = self.d / "spend" / "spend-ledger.jsonl"
        self.spend.parent.mkdir()
        (self.spend.parent / "key-usage-baseline.json").write_text(json.dumps({"usage": 10.0}))

    def args(self, *extra):
        return or_call.parser().parse_args(
            ["--key-file", str(self.key), "--spend-ledger", str(self.spend), "--seat", "maker", "--log", str(self.log), "--model",
             "deepseek/deepseek-v4.1-flash-1017", "--tag", "deepinfra/fp8", "--pin-provider", "DeepInfra",
             "--messages", str(self.msgs), "--out", str(self.out), "--gen-wait", "0", *extra])

    def run_ok(self, *extra):
        f = Fake(fx("chat-deepinfra.json"), [(200, fx("generation-deepinfra.json"))])
        return or_call.call(self.args(*extra), f, sleep=lambda s: None), f

    def test_request_shape_provider_block_and_header(self):
        rc, f = self.run_ok()
        self.assertEqual(rc, 0)
        self.assertEqual(f.sent[0]["url"], "https://openrouter.ai/api/v1/key")  # guard read, free
        post = f.sent[1]
        self.assertEqual(post["method"], "POST")
        self.assertEqual(post["url"], "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(post["body"]["provider"], {"order": ["deepinfra/fp8"], "allow_fallbacks": False, "zdr": True})
        self.assertEqual(post["headers"]["X-OpenRouter-Metadata"], "enabled")
        self.assertEqual(f.sent[2]["method"], "GET")
        self.assertIn("/generation?id=gen-", f.sent[2]["url"])

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
        bad = or_call.parser().parse_args(["--key-file", str(self.key), "--spend-ledger", str(self.spend), "--seat", "maker", "--log",
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
        a = or_call.parser().parse_args(["--key-file", str(self.key), "--spend-ledger", str(self.spend), "--seat", "maker", "--log", str(self.log),
                                         "--model", "deepseek/deepseek-v4.1-flash-1017", "--ledger", str(led),
                                         "--messages", str(self.msgs), "--gen-wait", "0"])
        f = Fake(fx("chat-deepinfra.json"), [(200, fx("generation-deepinfra.json"))])
        self.assertEqual(or_call.call(a, f, sleep=lambda s: None), 0)
        self.assertEqual(f.sent[1]["body"]["provider"]["order"], ["deepinfra/fp8"])


    # ------------------------------------------------------------ spend guard (approval item 6)
    def rows(self):
        return [json.loads(l) for l in self.spend.read_text().splitlines()] if self.spend.exists() else []

    def prefill(self, usd):
        self.spend.write_text(json.dumps({"event": "reserve", "id": "x", "worst_usd": usd}) + "\n"
                              + json.dumps({"event": "settle", "id": "x", "cost_usd": usd}) + "\n")

    def test_no_throttle_max_tokens_is_endpoint_max_and_no_reasoning_param(self):
        rc, f = self.run_ok()
        body = f.sent[1]["body"]
        self.assertEqual(body["max_tokens"], 131072)
        self.assertFalse({"reasoning", "reasoning_effort", "max_reasoning_tokens", "thinking"} & set(body))
        f2 = Fake(fx("chat-deepinfra.json"), [])
        self.assertEqual(or_call.call(self.args("--max-tokens", "4096"), f2), 2)
        self.assertEqual(f2.sent, [])

    def test_unknown_model_or_tag_refused_before_anything(self):
        f = Fake(fx("chat-deepinfra.json"), [])
        a = self.args(); a.tag = "deepinfra/fp8/priority"
        self.assertEqual(or_call.call(a, f), 2)
        self.assertEqual(f.sent, [])

    def test_reserve_then_settle_with_generation_cost(self):
        self.run_ok("--call", "maker_call_1")
        r = self.rows()
        self.assertEqual([x["event"] for x in r], ["reserve", "settle"])
        self.assertAlmostEqual(r[0]["worst_usd"], len(json.dumps(json.loads(self.msgs.read_text())).encode()) * 0.000000098 + 131072 * 0.000000294, places=7)
        self.assertEqual(r[1]["cost_usd"], 5.9388e-05)
        self.assertEqual(r[1]["source"], "generation.total_cost")
        self.assertAlmostEqual(or_call.ledger_spent(self.spend), 5.9388e-05)

    def test_refuses_when_ledger_near_bound_nothing_sent_nothing_logged(self):
        self.prefill(4.87)  # 4.87 + 0.0385 worst + 0.10 reserve >= 5.00
        f = Fake(fx("chat-deepinfra.json"), [(200, fx("generation-deepinfra.json"))])
        self.assertEqual(or_call.call(self.args(), f, sleep=lambda s: None), 6)
        self.assertEqual([s["method"] for s in f.sent], ["GET"])  # only the free key read
        self.assertFalse(self.log.exists())
        self.assertFalse(self.out.exists())
        self.assertEqual(len(self.rows()), 2)

    def test_allows_just_under_bound(self):
        self.prefill(4.85)  # 4.85 + 0.0385 + 0.10 = 4.9885 < 5
        rc, f = self.run_ok()
        self.assertEqual(rc, 0)

    def test_refuses_on_key_usage_delta_even_with_empty_ledger(self):
        f = Fake(fx("chat-deepinfra.json"), [], usage=14.90)  # baseline 10.0: 4.90 already spent on the key
        self.assertEqual(or_call.call(self.args(), f), 6)
        self.assertEqual([s["method"] for s in f.sent], ["GET"])

    def test_refuses_when_key_usage_unreadable_or_no_baseline(self):
        f = Fake(fx("chat-deepinfra.json"), [], usage=None)
        self.assertEqual(or_call.call(self.args(), f), 6)
        (self.spend.parent / "key-usage-baseline.json").unlink()
        f = Fake(fx("chat-deepinfra.json"), [])
        self.assertEqual(or_call.call(self.args(), f), 6)
        self.assertNotIn("POST", [s["method"] for s in f.sent])

    def test_unsettled_reserve_counts_at_worst_case(self):
        self.spend.write_text(json.dumps({"event": "reserve", "id": "y", "worst_usd": 4.88}) + "\n")
        self.assertAlmostEqual(or_call.ledger_spent(self.spend), 4.88)
        f = Fake(fx("chat-deepinfra.json"), [])
        self.assertEqual(or_call.call(self.args(), f), 6)

    def test_http_error_settles_zero_transport_error_settles_worst(self):
        chat = {"status": 400, "headers": {}, "body": {"error": {"message": "bad"}}}
        f = Fake(chat, [])
        self.assertEqual(or_call.call(self.args(), f), 3)
        self.assertEqual(self.rows()[-1]["cost_usd"], 0.0)

        class Boom(Fake):
            def request(s, method, url, headers, body, timeout=300):
                if method == "POST":
                    raise OSError("down")
                return Fake.request(s, method, url, headers, body, timeout)
        self.assertEqual(or_call.call(self.args(), Boom(chat, [])), 3)
        self.assertGreater(self.rows()[-1]["cost_usd"], 0.03)

    def test_test_mode_with_real_transport_sends_nothing(self):
        sent = []

        class OnlyKey:
            def request(s, method, url, headers, body, timeout=300):
                sent.append((method, url))
                if method == "GET" and url.endswith("/key"):
                    return 200, {}, json.dumps({"data": {"usage": 10.0}}).encode()
                raise AssertionError("test mode must not send " + method + " " + url)
        orig = or_call.Transport
        or_call.Transport = OnlyKey
        try:
            self.assertEqual(or_call.call(self.args(), None), 7)      # would allow -> 7, nothing sent
            self.prefill(4.95)
            self.assertEqual(or_call.call(self.args(), None), 6)      # refused -> 6
        finally:
            or_call.Transport = orig
        self.assertEqual({m for m, _ in sent}, {"GET"})
        self.assertFalse(self.log.exists())

    @unittest.skipUnless(os.environ.get("PLUMBLINE"), "set PLUMBLINE to a plumbline checkout (main b6ff8b5)")
    def test_finish_reason_logged_on_every_call(self):
        rc, _ = self.run_ok()
        self.assertEqual(rc, 0)
        e = json.loads(self.log.read_text())[-1]
        self.assertIn("finish_reason", e)
        self.assertEqual(e["finish_reason"], fx("chat-deepinfra.json")["body"]["choices"][0].get("finish_reason"))
        self.assertFalse(e["content_empty"])

    def test_finish_reason_length_with_empty_content_exit10_no_reply(self):
        chat = fx("chat-deepinfra.json"); chat["body"]["choices"][0]["finish_reason"] = "length"
        chat["body"]["choices"][0]["message"]["content"] = ""
        f = Fake(chat, [(200, fx("generation-deepinfra.json"))])
        rc = or_call.call(self.args(), f, sleep=lambda s: None)
        self.assertEqual(rc, 10)
        self.assertFalse(self.out.exists())
        e = json.loads(self.log.read_text())[-1]
        self.assertEqual((e["finish_reason"], e["content_empty"]), ("length", True))
        self.assertEqual([r["event"] for r in self.rows()], ["reserve", "settle"])

    def test_finish_reason_length_with_content_is_written(self):
        chat = fx("chat-deepinfra.json"); chat["body"]["choices"][0]["finish_reason"] = "length"
        f = Fake(chat, [(200, fx("generation-deepinfra.json"))])
        self.assertEqual(or_call.call(self.args(), f, sleep=lambda s: None), 0)
        self.assertTrue(self.out.exists())

    def test_transport_error_logs_finish_reason_null(self):
        class Boom(Fake):
            def request(s, method, url, headers, body, timeout=300):
                if method == "POST":
                    raise OSError("down")
                return super().request(method, url, headers, body, timeout)
        f = Boom(fx("chat-deepinfra.json"), [])
        self.assertEqual(or_call.call(self.args(), f, sleep=lambda s: None), 3)
        self.assertIsNone(json.loads(self.log.read_text())[-1]["finish_reason"])

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
        # main b6ff8b5: a call's time is the logger's own received_at (gap fix of job 2026-10-27)
        self.assertEqual(H.iso(calls[0].at), json.loads(self.log.read_text())[0]["received_at"][:19] + "Z")


if __name__ == "__main__":
    unittest.main()

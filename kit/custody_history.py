"""What a custody record may say about its own history, and where each fact must come from.

kit/emit_custody.py writes a custody/v1 record from a job's files. Iteration 1 trusted the Orchestrator's ledger
(inputs/custody.json) for times, endpoints and approvers. Real runs showed what that costs: round-minute times
typed after the fact (some later than the record itself), the model vendor's host recorded when every call went
through a router to someone else, and the orchestrating agent recorded as the Specialist. A checker cannot see
any of that, so the emitter must refuse to write it. This module holds those refusals. Stdlib only.

  TIMES      Every model call's time comes from its harness log: the logger's own `sent_at` / `received_at` when
             the log carries them, else the HTTP `Date` response header (server-set), else the response's
             `created` epoch. A hand-entered time for the same event is kept only as a cross-check: if it differs
             from the log by more than TOLERANCE_S the emitter refuses. Event order (frozenAt < startedAt <=
             producedAt <= checks <= close; frozenAt <= approvals <= startedAt; disposition >= the last check)
             and "nothing dated after the emit time" are refusals too.
  SEND/RECV  The harness log also carries the logger's own `sent_at` (when the request was sent) and
             `received_at` (when the reply came back). The maker's `startedAt` is the FIRST call's `sent_at`
             and `producedAt` is the LAST call's `received_at`; a check's `at` is its call's `received_at`.
             Each such time carries an `x-plumbline` source naming the log file and the line that carries it.
             A call with no logger `sent_at`/`received_at` is a hand time: its time would come from the
             response `Date` header (`server-header`) or the response `created` epoch (`response-created`).
             The emitter never writes it back to the log; it refuses it by default, and under
             `--allow-hand-times` lists it in `x-plumbline.hand_times[]`. `Call.hand_time_entries()` reports
             those entries.
  ENDPOINTS  custody SPEC section 4: `endpoint` is the host of the service that ANSWERED; "a router that passed
             the request on is not the service that answered". A call made straight to a provider: the request
             URL host. A call through an aggregator (AGGREGATORS, i.e. OpenRouter): the host the Orchestrator
             DECLARED for that seat's upstream provider (custody_ledger.py pin, logged live before the seat's
             first call), and only if the call's own /api/v1/generation reply NAMES that provider as the one that
             served it. The chat response's `provider` and `openrouter_metadata` may confirm or contradict that,
             but they never stand in for the generation reply: a reply that is present yet names no provider is
             CL1-15 evidence absent for that pass, and the emitter refuses. No pin, a pin declared after the
             first call, no generation reply, a generation reply naming no provider, no provider readable from
             the log, or any other provider serving or tried (a fallback): refused. Nothing ever defaults to the
             model vendor's host, no host is looked up from a table, and no endpoint is derived from routing
             config or a pin when the generation reply is missing or names no provider (custody CL1-15 would be
             absent; the emitter refuses rather than guess).
  ROUTING    Each aggregator call's request body must ask for the pin: provider.order of exactly one slug (the
             pinned one), provider.allow_fallbacks false, and provider.zdr true or provider.data_collection
             "deny". What was asked is recorded; a request that did not ask for it is a hard GAP, not a refusal
             (see docs/custody-emission.md, 'Routing request').
  APPROVALS  An approval is a record of who approved, not a signature. It counts only from a party who is not
             the orchestrating agent (inputs `orchestrator`) and not a model (the maker, an evaluator, or
             `kind: "model"`). An agent may appear only when marked `kind: "agent"` WITH `adopted` set (a
             published document it adopted). A name that reads like an agent but is not marked is refused.
  REVISION   The emitter's own git commit and tree are recorded; a dirty tree (outside dot-plumbline/, which
             is job state) or a mismatch with the stated revision (--expect-revision or
             $PLUMBLINE_EXPECT_REVISION, commit or tree, >= 7 hex) is refused.
"""
from __future__ import annotations
import json, os, re, subprocess
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

# A hand-entered time may differ from the harness log by at most this many seconds. 60 s absorbs a time typed
# to the minute (truncation loses up to 59 s) and ordinary clock skew between the harness host and the server;
# it does not absorb a time typed from memory minutes later, which is the failure it exists to catch.
TOLERANCE_S = 60

# Request hosts that pass a request on to someone else. Their host is never a custody endpoint.
AGGREGATORS = {"openrouter.ai": "openrouter", "api.openrouter.ai": "openrouter"}

# Where an aggregator's log can say who served a call. All three are OpenRouter's documented fields:
#   response `provider`              the provider display name on a sync response (openapi.json: "the `provider`
#                                    field of sync responses"; not listed in ChatResult's schema)
#   response `openrouter_metadata`   opt-in (request header X-OpenRouter-Metadata: enabled): endpoints.available[]
#                                    {provider, selected} and attempts[] {provider, model, status}
#   `generation` (harness-logged)    GET https://openrouter.ai/api/v1/generation?id=<response id>: data.provider_name
#                                    and data.provider_responses[] (every provider tried)
# Headers are not read: OpenRouter documents no provider header.
#
# Only the generation reply is EVIDENCE that a provider answered (CL1-15). The response fields may confirm or
# contradict it; a generation reply that is absent, or present and naming no provider, is refused.

# Words that mark a name as an agent's rather than a person's (whole words, case-insensitive).
AGENT_WORDS = ("agent", "bot", "assistant", "orchestrator", "chief of staff", "llm", "gpt", "claude", "gemini",
               "grok", "copilot", "chatbot", "automation")

HOST = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")
RFC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


class Refusals:
    """Facts the record would misstate. Any one of them and nothing is written."""
    def __init__(self):
        self.rows: list[tuple[str, str]] = []

    def add(self, kind: str, msg: str) -> None:
        self.rows.append((kind, msg))

    def __bool__(self):
        return bool(self.rows)


def parse_ts(v) -> datetime | None:
    if isinstance(v, str) and RFC.match(v):
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    return None


def iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hdr(h: dict, name: str):
    for k, v in (h or {}).items():
        if k.lower() == name.lower():
            return v
    return None


class Call:
    def __init__(self, log: str, i: int, raw: dict, lines: list[str] | None = None):
        self.log, self.i, self.raw = log, i, raw
        self.lines = lines or []
        req, resp = raw.get("request") or {}, raw.get("response") or {}
        hdrs = raw.get("response_headers") or raw.get("headers") or {}
        self.name = raw.get("call") or raw.get("name")
        self.url = req.get("url") or raw.get("url")
        self.host = (urlparse(self.url).hostname or "").lower() if self.url else None
        self.model = resp.get("model") or req.get("model")
        self.served, self.tried = served_by(raw)
        self.gen_served, self.gen_tried = generation_names(raw)
        self.generation_names_provider = bool(self.gen_served)
        self.provider = next(iter(self.served.values()), None)
        self.routing = routing_request(raw)
        self.sent = parse_ts(raw.get("sent_at"))
        self.received = parse_ts(raw.get("received_at"))
        self.has_generation = isinstance(raw.get("generation"), dict)
        d = _hdr(hdrs, "Date")
        try:
            self.date = parsedate_to_datetime(d).astimezone(timezone.utc) if d else None
        except (TypeError, ValueError):
            self.date = None
        c = resp.get("created")
        self.created = datetime.fromtimestamp(c, timezone.utc) if isinstance(c, (int, float)) else None
        self.at = self.received or self.date or self.created
        self.started = self.sent or self.created or self.date
        if self.received:
            self.at_basis = "received_at"
        elif self.date:
            self.at_basis = "response Date header"
        elif self.created:
            self.at_basis = "response created"
        else:
            self.at_basis = None

    @property
    def label(self) -> str:
        return f"{self.log}#{self.name or self.i}"

    def _line_of(self, value, key: str | None = None) -> int | None:
        """The 1-based line of this call's log that carries `value` (optionally under `"key":`)."""
        if value in (None, ""):
            return None
        vs = str(value)
        pat = f'"{key}"' if key else None
        hits = [n for n, ln in enumerate(self.lines, 1) if vs in ln and (pat is None or pat in ln)]
        if not hits:
            hits = [n for n, ln in enumerate(self.lines, 1) if vs in ln]
        if not hits:
            return None
        return hits[min(self.i, len(hits) - 1)]

    def source_of(self, key: str) -> str | None:
        n = self._line_of(self.raw.get(key), key)
        return f"{self.log}:{n}" if n else None

    def source_started(self) -> str | None:
        if self.sent:
            return self.source_of("sent_at")
        n = self._line_of((self.raw.get("response") or {}).get("created"), "created")
        if n:
            return f"{self.log}:{n}"
        n = self._line_of(_hdr(self.raw.get("response_headers") or self.raw.get("headers") or {}, "Date"), "Date")
        return f"{self.log}:{n}" if n else None

    def source_at(self) -> str | None:
        if self.received:
            return self.source_of("received_at")
        n = self._line_of(_hdr(self.raw.get("response_headers") or self.raw.get("headers") or {}, "Date"), "Date")
        if n:
            return f"{self.log}:{n}"
        n = self._line_of((self.raw.get("response") or {}).get("created"), "created")
        return f"{self.log}:{n}" if n else None

    def hand_time_entries(self) -> list[dict]:
        """Entries for `x-plumbline.hand_times[]` when the logger did not stamp sent_at/received_at.

        The time used is the response `Date` header (`server-header`) or the response `created` epoch
        (`response-created`), exactly as `Call.started` / `Call.at` read them. The emitter must not write
        these back to the log (T7)."""
        out = []
        resp = self.raw.get("response") if isinstance(self.raw.get("response"), dict) else {}
        hdrs = self.raw.get("response_headers") or self.raw.get("headers") or {}
        base = f"{self.log}#{self.name or self.i}"
        if self.sent is None:
            if self.created:
                n = self._line_of(resp.get("created"), "created")
                out.append({"field": f"{base}.sent_at", "file": self.log, "line": n,
                            "source": "response-created"})
            elif self.date:
                n = self._line_of(_hdr(hdrs, "Date"), "Date")
                out.append({"field": f"{base}.sent_at", "file": self.log, "line": n,
                            "source": "server-header"})
        if self.received is None:
            if self.date:
                n = self._line_of(_hdr(hdrs, "Date"), "Date")
                out.append({"field": f"{base}.received_at", "file": self.log, "line": n,
                            "source": "server-header"})
            elif self.created:
                n = self._line_of(resp.get("created"), "created")
                out.append({"field": f"{base}.received_at", "file": self.log, "line": n,
                            "source": "response-created"})
        return out


def read_log(path: Path, ref: Refusals | None = None, who: str = "log") -> list[Call]:
    """A harness log: one JSON object per call, a JSON list of them, or JSON Lines.

    `path` may be a `str` or a `Path` (a caller that hands over the string from a job's inputs works, P1).
    `ref` and `who` are optional so a reader that only wants the calls can call `read_log(path)`:
    refusals then go to a throwaway Refusals(). Every caller that passes its own Refusals keeps working
    unchanged."""
    path = Path(path)
    if ref is None:
        ref = Refusals()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        ref.add("harness-log", f"{who}: harness log {path.name} unreadable ({exc})"); return []
    lines = text.splitlines()
    try:
        doc = json.loads(text)
        items = doc if isinstance(doc, list) else [doc]
    except ValueError:
        try:
            items = [json.loads(ln) for ln in text.splitlines() if ln.strip()]
        except ValueError:
            ref.add("harness-log", f"{who}: {path.name} is not a JSON harness log (request/response/response_headers "
                                   f"per call), so no time or endpoint can be read from it")
            return []
    calls = [Call(path.name, i, it, lines) for i, it in enumerate(items) if isinstance(it, dict) and "request" in it]
    if not calls:
        ref.add("harness-log", f"{who}: {path.name} records no call (no object with a `request`)")
    for c in calls:
        if c.at is None:
            ref.add("time", f"{who}: {c.label} carries neither a response Date header nor a `created` time; "
                            f"its time cannot be read from the log")
        elif c.created and c.date and (c.created - c.date).total_seconds() > TOLERANCE_S:
            ref.add("time", f"{who}: {c.label} says it was created at {iso(c.created)}, after its own response "
                            f"Date {iso(c.date)}: the log contradicts itself")
    return calls


def fill_logger_times(path: Path) -> bool:
    """Deprecated: the emitter never writes its inputs (T7).

    Kept as a no-op so a caller that still imports it cannot dirty a harness log. The emitter reads a call
    with no logger `sent_at`/`received_at` as a hand time and either refuses it or lists it under
    `--allow-hand-times`; see `Call.hand_time_entries()`."""
    return False


def norm(v) -> str:
    return re.sub(r"[^a-z0-9]", "", str(v or "").lower())


def generation_names(raw: dict) -> tuple[dict, list]:
    """({source: provider that served}, [providers tried]) as the /api/v1/generation reply alone states them."""
    g = raw.get("generation") if isinstance(raw.get("generation"), dict) else None
    if g is None:
        return {}, []
    g = g.get("data") if isinstance(g.get("data"), dict) else g
    served = {}
    if g.get("provider_name"):
        served["generation provider_name"] = str(g["provider_name"])
    tried = [str(x.get("provider_name") or x.get("provider")) for x in (g.get("provider_responses") or [])
             if isinstance(x, dict) and (x.get("provider_name") or x.get("provider"))]
    return served, tried


def served_by(raw: dict) -> tuple[dict, dict]:
    """({source: provider that served the call}, {source: [providers tried]}) as the log states them."""
    resp = raw.get("response") if isinstance(raw.get("response"), dict) else {}
    served, tried = {}, {}
    if resp.get("provider"):
        served["response provider"] = str(resp["provider"])
    om = resp.get("openrouter_metadata") if isinstance(resp.get("openrouter_metadata"), dict) else {}
    sel = [e.get("provider") for e in ((om.get("endpoints") or {}).get("available") or [])
           if isinstance(e, dict) and e.get("selected") and e.get("provider")]
    if sel:
        served["openrouter_metadata.endpoints selected"] = str(sel[-1])
    att = [str(a.get("provider")) for a in (om.get("attempts") or []) if isinstance(a, dict) and a.get("provider")]
    if att:
        tried["openrouter_metadata.attempts"] = att
    gserved, gtried = generation_names(raw)
    served.update(gserved)
    if gtried:
        tried["generation provider_responses"] = gtried
    return served, tried


def routing_request(raw: dict) -> dict | None:
    """The request body's `provider` preferences, or None when the log does not carry the request body."""
    req = raw.get("request") if isinstance(raw.get("request"), dict) else {}
    body = req.get("body", req.get("json"))
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except ValueError:
            body = None
    if not isinstance(body, dict):
        body = req if any(k in req for k in ("messages", "provider", "input", "prompt")) else None
    if body is None:
        return None
    pv = body.get("provider") if isinstance(body.get("provider"), dict) else {}
    out = {k: pv.get(k) for k in ("order", "allow_fallbacks", "zdr", "data_collection", "only") if k in pv}
    if isinstance(body.get("models"), list):
        out["models"] = body["models"]
    return out


def pin_matches(name, pin: dict) -> bool:
    """A provider name from the log is the pinned provider: its display name, or its slug's provider part."""
    n = norm(name)
    return bool(n) and n in {norm(pin.get("provider")), norm(str(pin.get("slug") or "").split("/")[0])}


def endpoint_of(c: Call, ref: Refusals, who: str, pin: dict | None = None) -> tuple[str | None, dict]:
    """The host that answered this call, and how that was read. `pin`: the seat's declared provider pin."""
    if not c.host:
        ref.add("endpoint", f"{who}: {c.label} names no request URL, so the service that answered is unknown")
        return None, {}
    if c.host not in AGGREGATORS:
        if pin:
            ref.add("endpoint", f"{who}: {c.label} went to {c.host}, but this seat's provider pin says its calls go "
                                f"via {pin.get('via')} to {pin.get('provider')!r}; the log contradicts the pin")
            return None, {}
        return c.host, {"endpoint_basis": "request URL host", "request_host": c.host}
    route = {"aggregator": c.host, "upstream_provider": c.provider}
    if not pin:
        ref.add("endpoint", f"{who}: {c.label} went to the aggregator {c.host} and no provider pin was declared for "
                            f"this seat (custody_ledger.py pin, before its first call); the emitter will not guess "
                            f"which host answered (custody SPEC 4: a router is not the service that answered)")
        return None, route
    if not c.served:
        ref.add("endpoint", f"{who}: {c.label} went to {c.host} and the log does not say which provider served it "
                            f"(no response `provider`, no `openrouter_metadata`, no logged /api/v1/generation "
                            f"stats); the pin to {pin.get('provider')!r} cannot be confirmed and the emitter will "
                            f"not guess")
        return None, route
    if not c.has_generation:
        ref.add("endpoint", f"{who}: {c.label} went to {c.host} but the log carries no /api/v1/generation reply, so "
                            f"the provider that answered is not evidenced (custody CL1-15); the emitter will not "
                            f"derive the endpoint from the provider pin or routing config")
        return None, route
    if not c.generation_names_provider:
        ref.add("endpoint", f"{who}: {c.label} went to {c.host} but its /api/v1/generation reply names no provider, "
                            f"so which provider answered is not evidenced (custody CL1-15 absent for this pass); "
                            f"the emitter will not derive the endpoint from the provider pin or routing config")
        return None, route
    other = {src: n for src, n in c.served.items() if not pin_matches(n, pin)}
    if other:
        said = ", ".join(f"{n!r} ({src})" for src, n in other.items())
        ref.add("endpoint", f"{who}: {c.label} was served by {said}, not the pinned provider {pin.get('provider')!r} "
                            f"({pin.get('slug')}): a fallback to another provider; the record would name "
                            f"{pin.get('host')} for a call it did not answer")
        return None, route
    tried = sorted({n for ns in c.tried.values() for n in ns if not pin_matches(n, pin)})
    if tried:
        ref.add("endpoint", f"{who}: {c.label} was also sent to {', '.join(map(repr, tried))} "
                            f"({', '.join(c.tried)}), not only the pinned provider {pin.get('provider')!r}: a fallback "
                            f"was attempted, so the prompt reached a provider the pin excludes")
        return None, route
    route.update({"provider_slug": pin.get("slug"),
                  "endpoint_basis": f"declared pin ({pin.get('declaredAt')}) to {pin.get('provider')!r} at "
                                    f"{pin.get('host')}, served-by confirmed from {', '.join(sorted(c.gen_served))}"})
    return pin.get("host"), route


def routing_problems(r: dict | None, pin: dict) -> list[str]:
    """What a pinned, ZDR routing request lacks. Empty = it asked for exactly the pin, no fallbacks, ZDR/deny."""
    if r is None:
        return ["the log does not carry the request body, so the routing request cannot be read"]
    out = []
    show = lambda v: "absent" if v is None else repr(v)    # noqa: E731
    order = r.get("order")
    if not (isinstance(order, list) and len(order) == 1):
        out.append(f"provider.order is {show(order)}, not exactly one provider")
    elif str(order[0]).lower() != str(pin.get("slug") or "").lower():
        out.append(f"provider.order names {order[0]!r}, not the pinned slug {pin.get('slug')!r}")
    if r.get("allow_fallbacks") is not False:
        out.append(f"provider.allow_fallbacks is {show(r.get('allow_fallbacks'))}, not false (OpenRouter's default is "
                   f"true: other providers may serve)")
    if r.get("zdr") is not True and r.get("data_collection") != "deny":
        out.append(f"neither provider.zdr true nor provider.data_collection \"deny\" (zdr {show(r.get('zdr'))}, "
                   f"data_collection {show(r.get('data_collection'))})")
    if isinstance(r.get("models"), list) and len(r["models"]) > 1:
        out.append(f"models lists {len(r['models'])} models: a model fallback was allowed")
    return out


def model_matches(log_model, identifier) -> bool:
    if not log_model or not identifier:
        return False
    lm, ident = str(log_model).lower(), str(identifier).lower()
    return lm == ident or lm.endswith("/" + ident)


def cross_check(ref: Refusals, field: str, hand, derived: datetime | None, source: str) -> None:
    """A hand-entered time is a claim; the log is the evidence. Beyond TOLERANCE_S, refuse."""
    if hand in (None, "") or derived is None:
        return
    h = parse_ts(hand)
    if h is None:
        ref.add("time", f"{field}: hand-entered {hand!r} is not RFC 3339 UTC (...Z)"); return
    delta = (h - derived).total_seconds()
    if abs(delta) > TOLERANCE_S:
        ref.add("time", f"{field}: hand-entered {hand} but {source} puts it at {iso(derived)} "
                        f"({delta:+.0f} s; tolerance ±{TOLERANCE_S} s)")


def _norm(s) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def same_party(a, b) -> bool:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    return na == nb or f" {nb} " in f" {na} " or f" {na} " in f" {nb} "


def looks_agent(name) -> str | None:
    n = f" {_norm(name)} "
    for w in AGENT_WORDS:
        if f" {_norm(w)} " in n:
            return w
    return None


def check_approval(a: dict, i: int, ci: dict, packet: dict, ref: Refusals) -> dict:
    """Refuse an approval that is not a record of a non-agent, non-model party (or a marked, adopting agent)."""
    role, by, kind = a.get("role"), a.get("by"), (a.get("kind") or "person")
    where = f"bar.approvals[{i}] ({role})"
    orch = ci.get("orchestrator") or {}
    orch_names = [n for n in [orch.get("name"), *(orch.get("aliases") or [])] if n]
    if not orch_names:
        ref.add("approval", f"{where}: the custody inputs do not name the orchestrating agent (`orchestrator`: "
                            f"{{name, aliases}}), so this approval cannot be shown not to be its")
    if not by:
        ref.add("approval", f"{where}: names no approver"); return {"kind": kind}
    if any(same_party(by, n) for n in orch_names):
        ref.add("approval", f"{where} is by {by!r}, the orchestrating agent. An approval counts only from someone "
                            f"who is not the orchestrator and not a model; the {role} must approve themselves")
        return {"kind": kind}
    m = ci.get("maker") or {}
    models = [m.get("name"), (m.get("model") or {}).get("identifier")] if m.get("kind") == "model" else []
    for e in ci.get("evaluators") or []:
        if e.get("kind") == "model":
            models += [e.get("name"), e.get("id"), (e.get("model") or {}).get("identifier")]
    if kind == "model" or any(same_party(by, n) for n in models if n):
        ref.add("approval", f"{where} is by {by!r}, a model; a model's output is not an approval")
        return {"kind": kind}
    if kind == "agent":
        ad = a.get("adopted")
        if not (isinstance(ad, dict) and ad.get("document") and ad.get("version")):
            ref.add("approval", f"{where} is by the agent {by!r} with adopted={ad!r}; an agent's approval counts "
                                f"only as the adoption of a published document (`adopted`: {{document, version}})")
    elif kind == "person":
        w = looks_agent(by)
        if w:
            ref.add("approval", f"{where} is by {by!r}, which reads as an agent identity ({w!r}); refused unless "
                                f"marked kind: \"agent\" with `adopted` set, or approved by the person themselves")
    else:
        ref.add("approval", f"{where}: kind {kind!r} is not person, agent or model")
    seat = packet.get(role) if role in ("buyer", "specialist") else None
    if isinstance(seat, str) and seat and not same_party(by, seat):
        ref.add("approval", f"{where} is by {by!r} but the job's packet names its {role} as {seat!r}; one of them "
                            f"misstates who held the seat")
    return {"kind": kind}


def git(args, cwd) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


def revision(here: Path, job: Path, expect: str | None, ref: Refusals) -> dict:
    """The emitter's own commit and tree, refused when dirty or not the stated revision."""
    try:
        top = Path(git(["rev-parse", "--show-toplevel"], here).strip())
        commit = git(["rev-parse", "HEAD"], top).strip()
        tree = git(["rev-parse", "HEAD^{tree}"], top).strip()
        status = git(["status", "--porcelain=v1", "-z", "--untracked-files=all"], top)
    except (OSError, subprocess.CalledProcessError) as exc:
        ref.add("revision", f"the emitter is not running from a readable git checkout ({str(exc).strip()[:120]}); "
                            f"its revision cannot be recorded, so no record is written")
        return {}
    try:
        job_rel = job.resolve().relative_to(top.resolve()).as_posix()
    except ValueError:
        job_rel = None
    dirty = []
    for ent in status.split("\0"):
        if len(ent) < 4:
            continue
        p = ent[3:]
        if p.startswith("dot-plumbline/") or (job_rel and (p == job_rel or p.startswith(job_rel + "/"))):
            continue                                  # job state, not the emitter's code
        if "__pycache__/" in p or p.endswith(".pyc"):
            continue                                  # a bytecode cache is not a change to the code
        dirty.append(ent[:2].strip() + " " + p)
    if dirty:
        ref.add("revision", f"the emitter's tree is dirty at {commit[:12]} ({len(dirty)} change(s) outside "
                            f"dot-plumbline/, e.g. {', '.join(dirty[:3])}); a record must name code that exists "
                            f"as a commit")
    exp = (expect or "").strip().lower()
    if exp:
        if not re.fullmatch(r"[0-9a-f]{7,40}", exp):
            ref.add("revision", f"stated revision {expect!r} is not 7-40 hex")
        elif not (commit.startswith(exp) or tree.startswith(exp)):
            ref.add("revision", f"stated revision {exp} matches neither the emitter's commit {commit[:12]} nor its "
                                f"tree {tree[:12]}")
    return {"commit": commit, "tree": tree, "dirty": bool(dirty), "stated": exp or None}

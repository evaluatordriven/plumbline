#!/usr/bin/env python3
"""Emit a custody/v1 record (an in-toto Statement) for a job that reached a terminal state.

WHY THIS EXISTS. A Plumbline close writes the §5 records, the packet's end-of-job facts and the run-log row. None
of that can be read by someone outside Plumbline: it is Plumbline's own shape, checked against a corpus a stranger
does not have. custody/v1 (evaluatordriven/custody, SPEC.md section 4) is the public shape for the same facts —
who set the bar and when, who approved that exact bar, who made the work, who read it, beside which controls, and
what the approver decided. This emitter writes that record from the job's own files, so a stranger with only the
public checker (custody checker/check.py) and the files can re-read the job.

WHAT IT WILL NOT DO.
  - It never fabricates. Every digest is computed here from a file that exists; a fact Plumbline has no source
    for is left null/absent and NAMED in `x-plumbline.gaps` with the reason, and the exit code says so.
  - It never infers the disposition from the verdict. disposition.state is the packet's `disposition_state`
    (written by `plumbline_job.py close --disposition`). Plumbline's verdict rides only in x-plumbline.verdict.
  - It never writes a remedy. A remedy appears (under x-plumbline.remedy) only when the custody inputs name the
    evaluator evidence file it came from AND that file contains it verbatim.
  - It adds no key outside custody section 4 except under `x-` (SPEC section 4: producer fields only under x-).
  - It never hard-codes the level. levelClaimed, spread, run numbers, evaluators and harness logs all come
    from the inputs, so a CL2 record (spread, run >= 2, a different-family evaluator) needs no code change.
  - It needs no corpus, no ~/.hermes and no credentials: stdlib only.
  - It never writes its inputs (T7): a harness log is read, never rewritten.

SPEC VERSION. predicate.specVersion is the version of the custody document the job attests: the checkout
named by `inputs/custody.json: custody_spec`, whose SPEC.md `**Version X.Y.Z**` line is read, digested and
recorded under x-plumbline.spec_version {source, path, sha256, origin}. A job whose artifact is not a
custody tree carries `--spec-version X.Y.Z` (origin "--spec-version"). With neither, or with a document
that cannot be read or declares no version, the emitter REFUSES (kind `spec-version`, exit 3) and writes
nothing: it never falls back to the flag, to a literal, or to a guess. If both are given and disagree, it
refuses rather than choose.

HAND TIMES. A time in the record whose only source is a hand is a HAND TIME: a ledger line (inputs/
custody-events.jsonl) with `writer: "hand"` or with no `writer` at all, a time typed into inputs/custody.json with
no ledger line behind it, or a server-set time from a harness log call with no logger `sent_at`/`received_at` (the
response `Date` header or its `created` epoch). The emitter REFUSES hand times by default: exit 3, kind
`hand-time`, every field named with its file:line, nothing written. `--allow-hand-times` writes the record, lists
each hand time in `x-plumbline.hand_times[]` and records the allowance in `x-plumbline.allowances.hand_times`. The
switch FLAGS hand times; it never verifies them, and it silences nothing else. It cannot admit a model evaluator's
check time at all: a call carrying neither a logger `received_at` nor a response `Date` header leaves only the
response `created` epoch, a machine's clock the logger never stamped, and that is refused (kind `check-time`) even
under the switch.

RELAYS ARE NOT APPROVALS. A `relay` ledger line is a report of something said elsewhere, never an approval. A
buyer approval whose only evidence is a relay line (no `approve --role buyer` ledger line and no buyer entry in
inputs/custody.json) is refused with kind `approval`, naming `buyer` (F1f): the record would otherwise count a
report as the buyer's consent.

SOURCES, in order of authority:
  packet.json                       job_id, terminal_state, outcome, disposition_state     (Plumbline)
  iteration-N-eval-record.json      the final iteration's §5 record: verdict, violations,
                                    instrument_in_force (rubric/runner digests), pass list  (Plumbline)
  passes/<pass_id>.json             each filed pass: status, channel, provider, model,
                                    family, scores, void_cause                              (Plumbline)
  inputs/<run>.json                 the run file of that iteration, for the evaluator's
                                    verbatim quotes only                                    (Plumbline)
  inputs/custody.json               the custody facts Plumbline does not otherwise hold:
                                    bar file and its freeze time, approvals (each naming
                                    the digest it approved), maker model and method file,
                                    evaluators and their model blocks, per-pass time/batch/
                                    run/evidence file, controls (case files), harness logs
                                    (external), retention, levelClaimed. See
                                    docs/custody-emission.md for its shape.     (the Orchestrator's ledger)
  inputs/custody-events.jsonl       the same events, stamped live by kit/custody_ledger.py;
                                    each time field carries its file:line source under x-plumbline,
                                    and generations/evaluations/relays/amendments/spend are carried
                                    into x-plumbline with their line sources (F1h)
  <harness logs>                    each model call: request, response, headers and the
                                    logger's sent_at/received_at; the maker's startedAt and
                                    producedAt are the first call's sent_at and the last
                                    call's received_at, each with its file:line source

    emit_custody.py --job-dir <job> [--inputs inputs/custody.json] [--out FILE | --out-dir DIR] [--print-only]
                    [--allow-hand-times] [--spec-version X.Y.Z]

Default output: <job>/custody/record.custody.json. --out-dir DIR writes DIR/<job_id>.custody.json.
Exit: 0 written with no hard gap · 1 written, but a field the custody schema requires had no source (named in
x-plumbline.gaps and printed) · 2 refused (no packet, unreadable inputs, the job is not at a terminal state) ·
3 refused because the record would misstate its own history (kit/custody_history.py): a hand-entered time that the
harness log contradicts, a hand time with no --allow-hand-times, a relay counted as a buyer approval, events out of
order or dated after the close/emission, an endpoint that is a router or a guess (an aggregator call needs a
provider pin declared before the seat's first call, every call must be served by that provider alone, and the
/api/v1/generation reply must NAME it), an approval by the orchestrating agent or a model, a predicate.specVersion
with neither a custody document nor --spec-version behind it, or an emitter tree that is dirty or not the stated
revision. A routing request that did not ask OpenRouter for the pin alone with no
fallback and ZDR is a hard gap (exit 1), not a refusal: the record is still true, and it shows what was asked.
Nothing is written on 2 or 3; an existing record is left as it was.
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import custody_history as H                      # noqa: E402

# The version this emitter was cut against. It is NOT what a record stamps: predicate.specVersion is read from
# the custody document the job attests (resolve_spec_version), because a literal here would stamp a version the
# document does not declare. It stays as the emitter's declared baseline so tools/check_version_claims.py can go
# on comparing it with tools/pin.json -- a claim that must be able to disagree.
SPEC_VERSION = "0.9.8"
STATEMENT = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://evaluatordriven.com/custody/v1"
TERMINALS = ("accepted", "needs_owner", "rejected")
VERDICTS = ("accept", "regenerate", "needs_owner", "reject")
LOCATORS = ("artifact_missed_standard", "standard_moved", "dimension_unauthorized", "frame_at_fault")
DISPOSITIONS = ("given", "not_yet_given", "declined")
OUTCOMES = ("conforms", "does_not_conform", "unobserved")
HERE = Path(__file__).resolve().parent
RFC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
LEDGER_REL = "inputs/custody-events.jsonl"


class Gaps:
    """Every fact the record needed and Plumbline had no source for. Hard = the custody schema requires it."""
    def __init__(self):
        self.rows: list[dict] = []

    def add(self, field: str, reason: str, hard: bool = True) -> None:
        self.rows.append({"field": field, "reason": reason, "hard": hard})

    @property
    def hard(self) -> list[dict]:
        return [r for r in self.rows if r["hard"]]


def file_digest(p: Path) -> str:
    return sha256(p.read_bytes()).hexdigest()


def emitter_stamp() -> str:
    """`kit/emit_custody.py@<sha12>` for the file that is running (the allowance's writer)."""
    try:
        d = sha256(Path(__file__).resolve().read_bytes()).hexdigest()[:12]
    except OSError:
        d = "0" * 12
    return f"kit/emit_custody.py@{d}"


def ledger_lines(job: Path) -> list[tuple[int, dict]]:
    """Every row of inputs/custody-events.jsonl, in file order, with its 1-based line number."""
    p = job / LEDGER_REL
    out: list[tuple[int, dict]] = []
    if p.is_file():
        for n, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if not ln.strip():
                continue
            try:
                e = json.loads(ln)
            except ValueError:
                continue
            if isinstance(e, dict):
                e["_line"] = n
                out.append((n, e))
    return out


def writer_source(e: dict) -> str | None:
    """How a ledger line was written: None = a tool, else the hand-time source it is."""
    w = e.get("writer")
    if w == "hand":
        return "ledger-hand"
    if w in (None, ""):
        return "ledger-no-writer"
    return None


def call_cost(c) -> float:
    """A harness call's billed cost, in the order the job's harness uses for its own settle lines: the
    generation reply's `data.total_cost` when present, else the chat reply's `usage.cost` (V5)."""
    raw = getattr(c, "raw", None)
    if not isinstance(raw, dict):
        return 0.0
    gen = raw.get("generation") if isinstance(raw.get("generation"), dict) else None
    if gen is not None:
        data = gen.get("data") if isinstance(gen.get("data"), dict) else gen
        v = data.get("total_cost") if isinstance(data, dict) else None
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    resp = raw.get("response") if isinstance(raw.get("response"), dict) else {}
    usage = resp.get("usage") if isinstance(resp.get("usage"), dict) else {}
    v = usage.get("cost") if isinstance(usage, dict) else None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return 0.0


def flag_calls(calls, hand: dict | None) -> None:
    """Every call of a harness log the emitter reads: a `.sent_at`/`.received_at` the logger did not stamp is a
    hand time (T7b), named with the server time's source and the file:line that carries it. Every call counts,
    not only the first and the last, and both fields (a log with no logger `sent_at` on its calls would otherwise
    hide them). The log is never rewritten: a call the logger stamped adds nothing."""
    if hand is None:
        return
    for c in calls:
        for e in c.hand_time_entries():
            hand[e["field"]] = e


def ledger_array(lines: list[tuple[int, dict]], event: str) -> list[dict]:
    """Every ledger line of `event`, verbatim, with its file:line source (F1h)."""
    return [{**{k: v for k, v in e.items() if k != "_line"}, "source": f"{LEDGER_REL}:{e['_line']}"}
            for _, e in lines if e.get("event") == event]


def spend_block(lines: list[tuple[int, dict]], calls) -> dict:
    """x-plumbline.spend: the calls sum (logs), the key delta (the spend line), total = max, tolerance 1e-4."""
    sp = None
    for _, e in lines:
        if e.get("event") == "spend":
            sp = e
    calls_sum = round(sum(call_cost(c) for c in calls), 6)
    key_delta = float(sp.get("key_delta_usd") or 0) if sp else 0.0
    return {"calls_sum_usd": calls_sum, "key_delta_usd": key_delta,
            "total_usd": max(calls_sum, key_delta), "tolerance_usd": 0.0001,
            "source": f"{LEDGER_REL}:{sp['_line']}" if sp else None}


def relay_only_buyer(ci: dict, packet: dict, lines: list[tuple[int, dict]]) -> bool:
    """A buyer approval is relay-only when a relay line is its only evidence: no `approve --role buyer` ledger
    line and no buyer entry in inputs/custody.json (F1f). A relay is a report, never an approval."""
    if not packet.get("buyer"):
        return False
    if not any(e.get("event") == "relay" for _, e in lines):
        return False
    bar_roles = {a.get("role") for a in (ci.get("bar") or {}).get("approvals") or [] if isinstance(a, dict)}
    ledger_roles = {e.get("role") for _, e in lines if e.get("event") == "approve"}
    return "buyer" not in bar_roles and "buyer" not in ledger_roles


def rel_file(job: Path, rel: str | None, field: str, gaps: Gaps, hard: bool = True) -> Path | None:
    if not rel:
        gaps.add(field, "not named in the custody inputs", hard); return None
    p = (job / rel)
    if not p.is_file():
        gaps.add(field, f"named file {rel!r} does not exist in the job", hard); return None
    return p


def digest_of(job: Path, rel: str | None, field: str, gaps: Gaps, hard: bool = True) -> dict | None:
    p = rel_file(job, rel, field, gaps, hard)
    return {"sha256": file_digest(p)} if p else None


def hexdigest(v, field: str, gaps: Gaps) -> dict | None:
    """A digest someone TYPED (an approval names the digest it approved): copied, never recomputed."""
    if isinstance(v, dict):
        v = v.get("sha256")
    if isinstance(v, str) and v.startswith("sha256:"):
        v = v[7:]
    if isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v):
        return {"sha256": v}
    gaps.add(field, "no sha256 recorded for what was approved (a digest is copied from the approval, never "
                    "computed by the emitter)")
    return None


def ts(v, field: str, gaps: Gaps, hard: bool = True):
    if isinstance(v, str) and RFC.match(v):
        return v
    gaps.add(field, "no RFC 3339 UTC time recorded" if v in (None, "") else f"{v!r} is not RFC 3339 UTC (...Z)", hard)
    return None


def line_in(path: Path, value, key: str | None = None) -> int | None:
    """The 1-based line of `path` that carries `value` (optionally under `"key":`), if any."""
    if value in (None, "") or not path.is_file():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    vs = str(value)
    hits = [n for n, ln in enumerate(lines, 1) if vs in ln and (key is None or f'"{key}"' in ln)]
    if not hits:
        hits = [n for n, ln in enumerate(lines, 1) if vs in ln]
    return hits[0] if hits else None


VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
SPEC_DECL_RE = re.compile(r"\*\*Version\s+(\d+\.\d+\.\d+)\b")


def spec_md_version(spec_md: Path) -> tuple[str | None, int | None]:
    """The version a custody `SPEC.md` declares (its `**Version X.Y.Z · ...**` line) and that line's number."""
    try:
        lines = spec_md.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None, None
    for n, ln in enumerate(lines, 1):
        hit = SPEC_DECL_RE.search(ln)
        if hit:
            return hit.group(1), n
    return None, None


def _git_out(args, cwd: Path) -> str | None:
    try:
        return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True,
                              check=True).stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def checkout_head(checkout: Path, ref: H.Refusals) -> None:
    """A checkout that names its own commit must be the commit its work tree is at (R2)."""
    own = _git_out(["rev-parse", "HEAD"], checkout)
    if not own:
        return
    top = _git_out(["rev-parse", "--show-toplevel"], checkout)
    if not top:
        return
    head = _git_out(["rev-parse", "HEAD"], Path(top))
    if head and head != own:
        ref.add("spec-version", f"the custody checkout {checkout} names commit {own[:12]} but the work tree at "
                                f"{top} is at {head[:12]}: a SPEC.md read beside the wrong commit is not the "
                                f"document the job attests")


def resolve_spec_version(job: Path, ci: dict | None, override: str | None,
                         ref: H.Refusals) -> tuple[str | None, dict]:
    """The version this record attests: the custody document the job names, else --spec-version, else a refusal.

    R1: `inputs/custody.json: custody_spec` points at a custody checkout; the record carries the version its
    SPEC.md declares, digested, with the line that declares it. R3: `--spec-version` is the fallback for a job
    whose artifact is not a custody tree. R2: with neither, or with a document that cannot be read, the emitter
    REFUSES (kind `spec-version`) rather than fall back to the flag or to a literal. Both are given and they
    disagree: refused, because a record can attest only one version.
    """
    given = (ci or {}).get("custody_spec")
    doc_version, block = None, {}
    if given:
        checkout = Path(str(given)).expanduser()
        if not checkout.is_absolute():
            checkout = job / checkout
        spec_md = checkout / "SPEC.md"
        if not checkout.is_dir():
            ref.add("spec-version", f"inputs/custody.json custody_spec {str(given)!r} is not a directory "
                                    f"({checkout}): the document the job attests cannot be read")
        elif not spec_md.is_file():
            ref.add("spec-version", f"the custody checkout {checkout} carries no SPEC.md: the version the job "
                                    f"attests cannot be read")
        else:
            doc_version, line = spec_md_version(spec_md)
            block = {"origin": "document", "path": str(checkout),
                     "source": f"{spec_md}:{line}" if line else str(spec_md),
                     "sha256": file_digest(spec_md)}
            if doc_version is None:
                ref.add("spec-version", f"{spec_md} declares no `**Version X.Y.Z**`: the version the job attests "
                                        f"cannot be read")
            else:
                checkout_head(checkout, ref)
    if given and doc_version is None:
        return None, block                     # a named document that cannot be read never falls back (R2)
    if override:
        version = str(override).strip()
        if not VERSION_RE.match(version):
            ref.add("spec-version", f"--spec-version {override!r} is not an X.Y.Z version")
            return None, block
        if doc_version is not None:
            if version != doc_version:
                ref.add("spec-version", f"--spec-version {version!r} disagrees with the document "
                                        f"{block.get('path')}/SPEC.md, which declares {doc_version!r}: the record "
                                        f"can attest only one version, and the emitter will not choose silently")
                return None, block
            return doc_version, block
        return version, {"origin": "--spec-version", "path": None,
                         "source": "--spec-version", "sha256": None}
    if doc_version is not None:
        return doc_version, block
    ref.add("spec-version", "the job names no custody document (inputs/custody.json: custody_spec) and no "
                            "--spec-version was given: predicate.specVersion would have no source, and the "
                            "emitter refuses rather than guess")
    return None, {}


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def final_record(job: Path) -> tuple[Path | None, dict | None]:
    recs = []
    for f in job.glob("iteration-*-eval-record.json"):
        m = re.match(r"iteration-(\d+)-eval-record\.json$", f.name)
        if m:
            recs.append((int(m.group(1)), f))
    if not recs:
        return None, None
    recs.sort()
    return recs[-1][1], load(recs[-1][1])


def run_for(job: Path, iteration) -> dict | None:
    d = job / "inputs"
    for f in sorted(d.glob("*.json")) if d.is_dir() else []:
        try:
            r = load(f)
        except Exception:
            continue
        if isinstance(r, dict) and "passes" in r and r.get("iteration") == iteration:
            return r
    return None


def model_block(m, field: str, gaps: Gaps):
    """custody `model`: {family, identifier, endpoint, readOnly} or null (a person / script)."""
    if m is None:
        return None
    out = {}
    for k in ("family", "identifier", "endpoint", "readOnly"):
        if k in m and m[k] not in (None, ""):
            out[k] = m[k]
        else:
            gaps.add(f"{field}.{k}", "not recorded in the custody inputs")
    if isinstance(out.get("family"), str) and not re.fullmatch(r"[a-z]+(-[a-z]+)*", out["family"]):
        gaps.add(f"{field}.family", f"{out['family']!r} is not a custody family (lowercase, hyphens, no version)")
    return out


def events_log(job: Path, ref: H.Refusals) -> dict:
    """inputs/custody-events.jsonl, written as things happen by kit/custody_ledger.py. Latest row per key wins."""
    p = job / LEDGER_REL
    out = {"_file": None, "approve": {}, "pin": {}}
    if not p.is_file():
        return out
    out["_file"] = {"name": LEDGER_REL, "sha256": file_digest(p)}
    for n, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not ln.strip():
            continue
        try:
            e = json.loads(ln)
        except ValueError:
            ref.add("time", f"{LEDGER_REL} line {n} is not JSON"); continue
        e["_line"] = n
        if e.get("event") == "approve":
            out["approve"][e.get("role")] = e
        elif e.get("event") == "pin":
            out["pin"][e.get("seat")] = e
        elif e.get("event"):
            out[e["event"]] = e
    return out


def round_records(job: Path) -> list[tuple[int, Path, dict]]:
    """The round records loop() wrote, in round order: (number, path, record)."""
    out = []
    for path in job.glob("round-*.json"):
        m = re.fullmatch(r"round-(\d+)\.json", path.name)
        if not m:
            continue
        try:
            body = load(path)
        except Exception:
            continue
        if isinstance(body, dict):
            out.append((int(m.group(1)), path, body))
    out.sort(key=lambda row: row[0])
    return out


def is_loop_finish(packet: dict, job: Path) -> bool:
    """True for a job loop() filed: its packet carries the finish, or it wrote round records."""
    return isinstance(packet.get("finish"), dict) or bool(round_records(job))


def _packet_blocks(packet: dict) -> list[dict]:
    """packet.json itself, then the finish/summary objects loop() nests the stamps under."""
    blocks = [packet]
    for key in ("finish", "summary"):
        if isinstance(packet.get(key), dict):
            blocks.append(packet[key])
    return blocks


def _first_stamp(packet: dict, names: tuple) -> str | None:
    for block in _packet_blocks(packet):
        for name in names:
            value = block.get(name)
            if isinstance(value, str) and value.strip():
                return value
    return None


def _instant_text(value) -> str | None:
    """The instant `value` names, spelled as the custody schema's timestamp (UTC, ...Z)."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return H.iso(parsed.astimezone(timezone.utc))


def _editable_files(job: Path, number: int | None = None) -> list[tuple[str, Path]]:
    """Every file under round-NN/editable/, as (job-relative path, path)."""
    if number is not None:
        bases = [job / ("round-%02d" % number) / "editable"]
    else:
        bases = sorted(path / "editable" for path in job.glob("round-*") if path.is_dir())
    found = []
    for base in bases:
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file():
                found.append((path.relative_to(job).as_posix(), path))
    found.sort(key=lambda row: row[0])
    return found


def build_finish(job: Path, packet: dict, gaps: Gaps, ref: H.Refusals, now: datetime,
                 expect: str | None, allow_hand: bool = False, ci: dict | None = None,
                 override: str | None = None) -> tuple[dict, Gaps, list[str]]:
    """A custody/v1 record for a finish loop() filed, from the files loop() wrote.

    loop() writes packet.json (the finish's stamps and the ratified packet's own
    fields) and one round-NN.json per round — each evaluator run with its
    `parsed` reading, the round's `reading` and pass rule — plus that round's
    snapshot under round-NN/editable/. Those files are the sources this record
    reads. A fact they do not hold — a frozen bar, an approval, a maker's name,
    an instrument pin, a control, a retention, a disposition — is left null and
    named in x-plumbline.gaps with `hard: false`: the run did not hold it, so it
    is not a hard gap, and nothing is invented to fill it.
    """
    xp: dict = {"job_id": packet.get("job_id") or job.name, "sources": {}}
    rev = H.revision(HERE, job, expect or os.environ.get("PLUMBLINE_EXPECT_REVISION") or None, ref)
    version, version_block = resolve_spec_version(job, ci or {}, override, ref)
    rounds = round_records(job)
    packet_path = job / "packet.json"

    # ---- the finish's own stamps, exactly as packet.json holds them ----
    started_raw = _first_stamp(packet, ("started_at", "startedAt"))
    ended_raw = _first_stamp(packet, ("ended_at", "endedAt", "producedAt"))
    started = _instant_text(started_raw)
    produced = _instant_text(ended_raw)
    if started is None:
        gaps.add("startedAt", "packet.json holds no start instant for this finish", False)
    if produced is None:
        gaps.add("producedAt", "packet.json holds no end instant for this finish", False)
    for field, raw, key in (("startedAt", started_raw, "started_at"),
                            ("producedAt", ended_raw, "ended_at")):
        if raw:
            n = line_in(packet_path, raw, key)
            if n:
                xp["sources"][field] = f"packet.json:{n}"

    # ---- subject: the artifact files the run wrote, under round-NN/editable/ ----
    best = packet.get("accepted_round")
    if not isinstance(best, int):
        best = packet.get("best_round")
    files = _editable_files(job, best if isinstance(best, int) else None) or _editable_files(job)
    subject = [{"name": rel, "digest": {"sha256": file_digest(path)}} for rel, path in files]
    if not subject:
        gaps.add("subject", "the run wrote no editable artifact file to name", False)

    # ---- facts the run did not hold: named, not hard, nothing invented ----
    bar = {"digest": None, "frozenAt": None, "author": None, "dimensions": [], "approvals": [],
           "publishedAt": None, "groundTruth": [], "dissent": []}
    for field, reason in (
        ("bar.digest", "the run wrote no frozen bar file, and its packet names none"),
        ("bar.frozenAt", "the run wrote no freeze time"),
        ("bar.author", "the run wrote no bar author"),
        ("bar.dimensions", "the run wrote no bar dimension"),
        ("bar.approvals", "the run recorded no approval"),
    ):
        gaps.add(field, reason, False)

    maker = {"name": None, "kind": None, "version": None, "method": None, "model": None}
    for key, reason in (
        ("name", "the packet's maker block names no name"),
        ("kind", "the packet's maker block names no kind"),
        ("version", "the packet's maker block names no version"),
        ("method", "the run wrote no maker method file"),
    ):
        gaps.add("maker." + key, reason, False)

    instrument = {"rubric": None, "runner": None}
    for key, reason in (
        ("rubric", "the run wrote no rubric file and pinned no rubric digest"),
        ("runner", "the run wrote no runner file and pinned no runner digest"),
    ):
        gaps.add("instrument." + key, reason, False)

    # ---- evaluators: what the packet's evaluator block says the run dispatched ----
    evaluator = packet.get("evaluator") if isinstance(packet.get("evaluator"), dict) else {}
    kind = evaluator.get("kind") if evaluator.get("kind") in ("person", "model", "script") else None
    name = evaluator.get("name") if isinstance(evaluator.get("name"), str) and evaluator.get("name") else None
    ev_id = evaluator.get("id") if isinstance(evaluator.get("id"), str) and evaluator.get("id") else (name or "evaluator")
    if name is None:
        gaps.add("evaluators[0].name", "the packet's evaluator block names no name", False)
    if kind is None:
        gaps.add("evaluators[0].kind", "the packet's evaluator block names no kind", False)
    evaluators = [{"id": ev_id, "name": name or ev_id, "kind": kind, "model": None, "script": None}]

    # ---- checks: what each round's evaluator read ----
    def reading_of(row: dict) -> dict:
        return row.get("reading") if isinstance(row.get("reading"), dict) else {}

    def dims_of(row: dict) -> list[dict]:
        found = [d for d in reading_of(row).get("dimensions") or [] if isinstance(d, dict)]
        if found:
            return found
        out = []
        for run in row.get("evaluator") or []:
            parsed = run.get("parsed") if isinstance(run, dict) else None
            if isinstance(parsed, dict):
                out.extend(d for d in parsed.get("dimensions") or [] if isinstance(d, dict))
        return out

    checks = []
    for number, path, row in rounds:
        at_raw = row.get("ended_at")
        at = _instant_text(at_raw)
        at_line = line_in(path, at_raw, "ended_at") if isinstance(at_raw, str) else None
        reading = reading_of(row)
        for dimension in dims_of(row):
            score = dimension.get("score")
            x = {"round": number, "record": path.name, "pass_rule": row.get("pass_rule"),
                 "verdict": reading.get("verdict"), "stop": row.get("stop"),
                 "observation": dimension.get("observation")}
            if at_line:
                x["at_source"] = f"{path.name}:{at_line}"
            checks.append({
                "dimension": dimension.get("name"),
                "evaluator": ev_id,
                "run": number,
                "batch": None,
                "at": at,
                "outcome": None,
                "score": score if isinstance(score, (int, float)) and not isinstance(score, bool) else None,
                "failureCondition": None,
                "evidence": None,
                "unobserved": None,
                "x-plumbline": x,
            })
    if checks:
        for field, reason in (
            ("checks.batch", "the run's round records name no batch"),
            ("checks.failureCondition", "the packet declares no per-dimension failure condition"),
            ("checks.outcome", "the run's round records carry a score, not a custody outcome per dimension"),
            ("checks.evidence", "the run wrote no evaluator evidence file"),
        ):
            gaps.add(field, reason, False)
    else:
        gaps.add("checks", "the run's round records carry no evaluator reading", False)

    # ---- violations: what each round's evaluator filed ----
    violations = []
    for number, path, row in rounds:
        for item in reading_of(row).get("violations") or []:
            if isinstance(item, dict):
                violations.append({
                    "dimension": item.get("dimension"),
                    "description": item.get("observation") or item.get("description") or "",
                    "x-plumbline": {"locator": item.get("class"), "id": item.get("id"),
                                    "round": number, "record": path.name},
                })

    gaps.add("controls", "the run's round records carry no control case", False)
    gaps.add("external", "the run wrote no harness log, so no CL1-15 evidence exists", False)
    gaps.add("retention", "the run recorded no retention location", False)

    disposition = {"state": None, "by": None, "at": None, "acknowledgesUnobserved": []}
    gaps.add("disposition.state", "the packet holds no disposition_state", False)
    gaps.add("disposition.by", "the run named no approver", False)
    gaps.add("disposition.at", "the run recorded no disposition time", False)

    separation = [s for s in packet.get("separation_gaps") or [] if isinstance(s, str)] \
        if isinstance(packet.get("separation_gaps"), list) else []

    verdict = None
    for _, _, row in rounds:
        found = reading_of(row).get("verdict")
        if found in VERDICTS:
            verdict = found
    xp["terminal_state"] = packet.get("terminal_state")
    if packet.get("outcome") is not None:
        xp["outcome"] = packet.get("outcome")
    xp["verdict"] = verdict
    if packet.get("stop") is not None:
        xp["stop"] = packet.get("stop")
    xp["round_count"] = len(rounds)
    xp["rounds"] = [{"round": number, "record": path.name, "sha256": file_digest(path)}
                    for number, path, _ in rounds]
    xp["evaluator_runs"] = [
        {"round": number, "exit": run.get("exit"), "output_sha256": run.get("output_sha256")}
        for number, _, row in rounds for run in (row.get("evaluator") or []) if isinstance(run, dict)
    ]
    spend = 0.0
    for _, _, row in rounds:
        cost = row.get("cost")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool):
            spend += float(cost)
    xp["spend"] = {"rounds_cost_usd": round(spend, 6), "source": "round-*.json cost"}

    level = packet.get("levelClaimed")
    if level not in ("CL1", "CL2", "CL3", "baseline"):
        level = "CL1"
    pred = {
        "specVersion": version,
        "levelClaimed": level,
        "bar": bar,
        "maker": maker,
        "startedAt": started,
        "producedAt": produced,
        "instrument": instrument,
        "evaluators": evaluators,
        "checks": checks,
        "controls": [],
        "disagreements": [],
        "violations": violations,
        "separationGaps": separation,
        "retention": None,
        "external": [],
        "disposition": disposition,
    }
    if xp.get("terminal_state") not in TERMINALS:
        gaps.add("x-plumbline.terminal_state", f"packet terminal_state is {xp.get('terminal_state')!r}")
    xp["schema"] = "plumbline/x-plumbline/v1"
    if version_block:
        xp["spec_version"] = version_block
    xp["emitter"] = {"name": "kit/emit_custody.py", "kit_revision": (rev.get("commit") or "")[:7] or None,
                     "commit": rev.get("commit"), "tree": rev.get("tree"), "dirty": rev.get("dirty"),
                     "statedRevision": rev.get("stated")}
    xp["time_tolerance_s"] = H.TOLERANCE_S
    xp["times"] = {"startedAt": "packet.json started_at", "producedAt": "packet.json ended_at"}
    xp["hand_times"] = []
    xp["timeSources"] = time_sources(pred, xp)
    xp["time_sources"] = dict(xp["timeSources"])
    check_order(pred, packet, {}, now, ref)
    xp["emittedAt"] = H.iso(now)
    xp["gaps"] = gaps.rows
    pred["x-plumbline"] = xp
    return ({"_type": STATEMENT, "subject": subject, "predicateType": PREDICATE_TYPE, "predicate": pred},
            gaps, [])


def build(job: Path, inputs_path: Path, ref: H.Refusals | None = None, now: datetime | None = None,
          expect: str | None = None, allow_hand: bool = False,
          spec_version: str | None = None) -> tuple[dict, Gaps, list[str]]:
    gaps, notes = Gaps(), []
    ref = ref if ref is not None else H.Refusals()
    now = now or datetime.now(timezone.utc).replace(microsecond=0)
    packet = load(job / "packet.json")
    have_inputs = inputs_path.is_file()
    if is_loop_finish(packet, job):
        # The round path reads the custody inputs for one thing only: the document the job attests. A malformed
        # inputs file is not this path's to police (it was never read here before), so it is treated as absent.
        round_ci = None
        if have_inputs:
            try:
                round_ci = load(inputs_path)
            except (ValueError, OSError):
                round_ci = None
        return build_finish(job, packet, gaps, ref, now, expect, allow_hand,
                            ci=round_ci if isinstance(round_ci, dict) else None, override=spec_version)
    ci = load(inputs_path) if have_inputs else None
    if ci is None:
        gaps.add("inputs/custody.json", f"no custody inputs at {inputs_path.relative_to(job) if inputs_path.is_relative_to(job) else inputs_path}: "
                 "bar, approvals, maker, evaluators, controls and retention have no source")
        ci = {}
    job_id = packet.get("job_id") or job.name
    xp: dict = {"job_id": job_id, "sources": {}}
    try:
        rel_inputs = inputs_path.relative_to(job).as_posix()
    except ValueError:
        rel_inputs = str(inputs_path)
    ev_dir = job / ci.get("evidence_dir", "custody/evidence")
    ev_log = events_log(job, ref)
    if ev_log["_file"]:
        xp["events_log"] = ev_log["_file"]
    lines = ledger_lines(job)
    hand: dict[str, dict] = {}

    def mark(field: str, file: str, line, source: str) -> None:
        hand[field] = {"field": field, "file": file, "line": line, "source": source}

    # ---- the emitter's own revision (refused when dirty or not the stated revision) ----
    rev = H.revision(HERE, job, expect or os.environ.get("PLUMBLINE_EXPECT_REVISION") or ci.get("emitter_revision"), ref)
    version, version_block = resolve_spec_version(job, ci, spec_version, ref)

    # ---- terminal state, verdict, disposition (three separate facts, three separate sources) ----
    xp["terminal_state"] = packet.get("terminal_state")
    if packet.get("outcome") is not None:
        xp["outcome"] = packet["outcome"]
    rec_path, rec = final_record(job)
    passes_src: list[dict] = []
    run = None
    if rec:
        xp["verdict"] = rec.get("verdict")
        xp["iteration"] = rec.get("iteration")
        xp["s5_record"] = {"name": rec_path.name, "sha256": file_digest(rec_path)}
        earlier = sorted(f.name for f in job.glob("iteration-*-eval-record.json") if f != rec_path)
        if earlier:
            xp["earlier_iterations"] = earlier
        if rec.get("pass_rule") is not None:
            xp["pass_rule"] = rec["pass_rule"]
        for pn in rec.get("passes") or []:
            pf = job / str(pn.get("artifact") or f"passes/{pn.get('pass_id')}.json")
            passes_src.append(load(pf) if pf.is_file() else {**pn, "_missing": str(pf.relative_to(job))})
        run = run_for(job, rec.get("iteration"))
    else:
        xp["verdict"] = ci.get("verdict")          # a readings job files no §5 record (kit/plumbline_job.py)
        if xp["verdict"] is None:
            gaps.add("x-plumbline.verdict", "no §5 record in the job and no verdict in the custody inputs", False)
    xp["disposition_source"] = "packet.json disposition_state"
    xp["packet"] = {"name": "packet.json", "sha256": file_digest(job / "packet.json")}

    # ---- subject: the artifact files, by digest ----
    files_dir = job / ci.get("files_dir", "custody/files")
    names = ci.get("subject")
    if names is None and files_dir.is_dir():
        names = sorted(str(p.relative_to(files_dir)) for p in files_dir.rglob("*") if p.is_file())
    subject = []
    for n in names or []:
        p = files_dir / n
        if p.is_file():
            subject.append({"name": n, "digest": {"sha256": file_digest(p)}})
        else:
            gaps.add(f"subject[{n}]", f"artifact file {n!r} not found under {files_dir.relative_to(job)}")
    if not subject:
        gaps.add("subject", "no artifact file to name")

    # ---- bar ----
    b = ci.get("bar") or {}
    bar_digest = digest_of(job, b.get("file"), "bar.digest", gaps)
    dims_in = b.get("dimensions") or []
    if not dims_in:
        gaps.add("bar.dimensions", "the custody inputs list no bar dimension")
    dims, fail_cond, pl_name = [], {}, {}
    for d in dims_in:
        dims.append({"id": d.get("id"), "criterion": d.get("criterion"), "scale": d.get("scale")})
        fail_cond[d.get("id")] = d.get("failureCondition")
        pl_name[d.get("plumbline_dimension", d.get("id"))] = d.get("id")
    approvals = []
    for i, a in enumerate(b.get("approvals") or []):
        xa = H.check_approval(a, i, ci, packet, ref)
        live = ev_log["approve"].get(a.get("role")) if have_inputs else None
        if live:
            src = writer_source(live)
            if src:
                mark(f"bar.approvals[{i}].at", LEDGER_REL, live.get("_line"), src)
        elif a.get("at"):
            mark(f"bar.approvals[{i}].at", rel_inputs, line_in(inputs_path, a.get("at"), "at"), "inputs-no-ledger")
        xa["time_source"] = "hand-entered"
        if live:
            # The live event is the source of the time. A value the inputs also state must agree with it; a field
            # the event does not carry is not compared (the ledger is not required to restate it).
            for k in ("by", "at"):
                if a.get(k) and live.get(k) and live.get(k) != a.get(k):
                    ref.add("time" if k == "at" else "approval",
                            f"bar.approvals[{i}].{k}: the ledger says {a.get(k)!r} but {LEDGER_REL} "
                            f"logged {live.get(k)!r} when it happened")
            xa["time_source"] = "logged live (inputs/custody-events.jsonl)"
            if live.get("at"):
                xa["at_source"] = f"{LEDGER_REL}:{live['_line']}"
        elif a.get("at"):
            n = line_in(inputs_path, a.get("at"), "at")
            if n:
                xa["at_source"] = f"{rel_inputs}:{n}"
        if xa.get("at_source"):
            xp["sources"][f"bar.approvals[{i}].at"] = xa["at_source"]
        approvals.append({"role": a.get("role"), "by": a.get("by"),
                          "barDigest": hexdigest(a.get("barDigest"), f"bar.approvals[{i}].barDigest", gaps),
                          "at": ts(a.get("at"), f"bar.approvals[{i}].at", gaps), "adopted": a.get("adopted"),
                          "x-plumbline": xa})
    if not approvals:
        gaps.add("bar.approvals", "no buyer/specialist approval recorded")
    # F1f: a relay is a report, never an approval. A buyer approval whose only evidence is a relay line is
    # refused as a missing approval: the emitter will not count the relay.
    if have_inputs and relay_only_buyer(ci, packet, lines):
        ref.add("approval", f"buyer: the buyer's approval exists only as a relay ({LEDGER_REL}); a relay is a "
                            f"report, not an approval (F1f). The buyer must approve directly: "
                            f"custody_ledger.py approve --role buyer, or a buyer entry in inputs/custody.json")
    ground = []
    for i, g in enumerate(b.get("groundTruth") or []):
        ground.append({"name": g.get("name"), "version": g.get("version"),
                       "digest": digest_of(job, g.get("file"), f"bar.groundTruth[{i}].digest", gaps)})
    # A live freeze/approval/disposition event is the source of its time, and a cross-check on the inputs' own
    # value. The events are read only when the custody inputs exist: they stamp and check the inputs' facts, and
    # a job emitted with no inputs at all is already reported in x-plumbline.gaps (it is not a refusal).
    fz = ev_log.get("freeze") if have_inputs else None
    if fz:
        if b.get("frozenAt") and fz.get("at") and fz.get("at") != b.get("frozenAt"):
            ref.add("time", f"bar.frozenAt: the ledger says {b.get('frozenAt')!r} but {LEDGER_REL} "
                            f"logged the freeze at {fz.get('at')!r}")
        if bar_digest and fz.get("bar_sha256") and fz["bar_sha256"] != bar_digest["sha256"]:
            ref.add("order", f"bar: frozen as {fz['bar_sha256'][:12]} ({LEDGER_REL}) but the bar file "
                             f"now hashes to {bar_digest['sha256'][:12]}: the bar changed after the freeze")
    frozen_at = b.get("frozenAt") or (fz or {}).get("at")
    if fz:
        src = writer_source(fz)
        if src:
            mark("bar.frozenAt", LEDGER_REL, fz.get("_line"), src)
    elif b.get("frozenAt"):
        mark("bar.frozenAt", rel_inputs, line_in(inputs_path, b.get("frozenAt"), "frozenAt"), "inputs-no-ledger")
    bar = {"digest": bar_digest, "frozenAt": ts(frozen_at, "bar.frozenAt", gaps),
           "author": b.get("author"), "dimensions": dims, "approvals": approvals,
           "publishedAt": b.get("publishedAt"), "groundTruth": ground, "dissent": b.get("dissent") or []}
    if fz and frozen_at:
        xp["sources"]["bar.frozenAt"] = f"{LEDGER_REL}:{fz['_line']}"
    elif b.get("frozenAt"):
        n = line_in(inputs_path, b.get("frozenAt"), "frozenAt")
        if n:
            xp["sources"]["bar.frozenAt"] = f"{rel_inputs}:{n}"
    if not b.get("author"):
        gaps.add("bar.author", "not recorded")

    # ---- maker ----
    m = ci.get("maker") or {}
    pm = packet.get("maker") if isinstance(packet.get("maker"), dict) else {}
    mk = maker_history(job, ev_dir, ci, m, ref, pin_for(ci, ev_log, "maker", ref), gaps, hand) if m.get("kind") == "model" else {}
    # A typed startedAt/producedAt is a hand time whether or not the maker has a logged call (V3): the tool's
    # time is the log's, and a time typed into custody.json has no tool behind it (as for pass and control times).
    if ci.get("startedAt"):
        mark("startedAt", rel_inputs, line_in(inputs_path, ci.get("startedAt"), "startedAt"), "inputs-no-ledger")
    if ci.get("producedAt"):
        mark("producedAt", rel_inputs, line_in(inputs_path, ci.get("producedAt"), "producedAt"), "inputs-no-ledger")
    # The endpoint comes only from the harness log (a direct call's URL host, or the pinned provider the
    # /api/v1/generation reply NAMES as the one that served it). A hand-entered endpoint in the inputs is never
    # used, and there is no fallback to routing config or a provider pin when the generation reply is missing or
    # names no provider.
    m_model = {k: v for k, v in (m.get("model") or {}).items() if k != "endpoint"}
    if mk.get("endpoint"):
        m_model["endpoint"] = mk["endpoint"]
    maker = {"name": m.get("name") or pm.get("engine"), "kind": m.get("kind"),
             "version": m.get("version") or pm.get("version"),
             "method": digest_of(job, m.get("method_file"), "maker.method", gaps),
             "model": model_block(m_model, "maker.model", gaps) if m.get("kind") == "model" else None}
    if mk:
        maker["x-plumbline"] = mk["x"]
        for f in ("startedAt", "producedAt"):
            src = (mk.get("x") or {}).get(f"{f}_source")
            if src:
                xp["sources"][f] = src
    for k in ("name", "kind", "version"):
        if not maker[k]:
            gaps.add(f"maker.{k}", "not recorded")

    # ---- instrument: the §5 record's own pinned hashes; files in the inputs must agree ----
    inst = (rec or {}).get("instrument_in_force") or {}
    instrument = {}
    for key, s5key, fkey in (("rubric", "rubric_sha256", "rubric_file"), ("runner", "code_sha256", "runner_file")):
        from_file = digest_of(job, (ci.get("instrument") or {}).get(fkey), f"instrument.{key}", Gaps())
        from_s5 = inst.get(s5key)
        if from_s5 and from_file and from_file["sha256"] != from_s5:
            gaps.add(f"instrument.{key}", f"the §5 record pins {from_s5[:12]} but the named file hashes to "
                                          f"{from_file['sha256'][:12]}: refusing to choose")
            instrument[key] = None
        elif from_s5 and re.fullmatch(r"[0-9a-f]{64}", str(from_s5)):
            instrument[key] = {"sha256": from_s5}
        elif from_file:
            instrument[key] = from_file
        else:
            gaps.add(f"instrument.{key}", "neither the §5 record nor the custody inputs pin it")
            instrument[key] = None

    # ---- evaluators ----
    evs, ev_calls, ev_ep = [], {}, {}
    for i, e in enumerate(ci.get("evaluators") or []):
        e_model = {k: v for k, v in (e.get("model") or {}).items() if k != "endpoint"}
        eh = {}
        if e.get("kind") == "model":
            eh = evaluator_history(job, ev_dir, ci, e, ref, pin_for(ci, ev_log, str(e.get("id")), ref), gaps, hand)
            ev_calls[e.get("id")], ev_ep[e.get("id")] = eh.get("calls", {}), eh.get("endpoint")
            if eh.get("endpoint"):
                e_model["endpoint"] = eh["endpoint"]
        ev = {"id": e.get("id"), "name": e.get("name"), "kind": e.get("kind"),
              "model": model_block(e_model, f"evaluators[{i}].model", gaps) if e.get("kind") == "model" else None}
        if e.get("kind") == "model" and eh.get("x"):
            ev["x-plumbline"] = eh["x"]
        if e.get("kind") == "script":
            s = e.get("script") or {}
            ev["script"] = {"name": s.get("name"), "author": s.get("author"),
                            "digest": digest_of(job, s.get("file"), f"evaluators[{i}].script.digest", gaps)}
        else:
            ev["script"] = None
        if e.get("kind") == "model" and maker.get("model") and ev["model"]:
            same = ev["model"].get("identifier") == maker["model"].get("identifier")
            if "sameModelAsMaker" in e and bool(e["sameModelAsMaker"]) != same:
                gaps.add(f"evaluators[{i}].sameModelAsMaker", "the inputs' value contradicts the identifiers; "
                                                               "the identifiers decide (CL1-6)", False)
            if same:
                ev["sameModelAsMaker"] = True
        evs.append(ev)
    if not evs:
        gaps.add("evaluators", "no evaluator recorded")
    ev_ids = {e["id"] for e in evs}
    all_calls = list(mk.get("_calls") or [])
    for d in ev_calls.values():
        all_calls += list(d.values())

    # ---- provider pins are tool-stamped times too (routing.<seat>.declaredAt) ----
    used_seats = set()
    if m.get("kind") == "model":
        used_seats.add("maker")
    for e in evs:
        if e.get("kind") == "model":
            used_seats.add(str(e.get("id")))
    for seat, live in (ev_log.get("pin") or {}).items():
        if seat in used_seats:
            src = writer_source(live)
            if src:
                mark(f"routing.{seat}.declaredAt", LEDGER_REL, live.get("_line"), src)

    # ---- separation gaps: the inputs' own, plus the same-family fact the model blocks show ----
    sep = list(ci.get("separationGaps") or [])
    mf = (maker.get("model") or {}).get("family")
    for e in evs:
        ef = (e.get("model") or {}).get("family")
        if mf and ef and ef == mf:
            line = f"evaluator {e['id']} ({e['name']}) shares model family '{ef}' with the maker"
            if not any(line in s for s in sep):
                sep.append(line)

    # ---- checks: one per (filed pass, bar dimension), from the final iteration's passes ----
    pfacts = ci.get("passes") or {}
    quotes = {}
    for p in (run or {}).get("passes") or []:
        for q in p.get("evidence") or []:
            quotes.setdefault((p.get("pass_id"), q.get("dimension")), []).append(q.get("quote"))
    scales = {d["id"]: d.get("scale") for d in dims}
    checks = []
    for p in passes_src:
        pid = p.get("pass_id")
        f = pfacts.get(pid)
        if p.get("_missing"):
            gaps.add(f"checks[{pid}]", f"the §5 record lists pass {pid} but {p['_missing']} is absent")
            continue
        if f is None:
            gaps.add(f"checks[{pid}]", f"no custody facts for pass {pid} (evaluator, time, batch, evidence)")
            continue
        scores = {pl_name.get(s.get("dimension"), s.get("dimension")): s.get("score") for s in p.get("scores") or []}
        dims_read = f.get("dimensions") or list(scores) or [d["id"] for d in dims]
        n_passes = sum(1 for q in pfacts.values() if q.get("evaluator") == f.get("evaluator"))
        # A typed `at` is a hand time whether or not a harness call is linked (T2c): the tool's time is the log's,
        # and a time typed into custody.json has no tool behind it. With a call linked, the typed value is also
        # cross-checked against the call below.
        if f.get("at"):
            mark(f"passes.{pid}.at", rel_inputs, line_in(inputs_path, f.get("at"), "at"), "inputs-no-ledger")
        call = link_call(ev_calls, f.get("evaluator"), f.get("call"),
                         "eval_artifact" if n_passes == 1 else None, f"passes.{pid}", ref)
        at_v, ep_v, xc = f.get("at"), f.get("endpoint"), {}
        if call is not None:
            H.cross_check(ref, f"passes.{pid}.at", f.get("at"), call.at, f"harness log {call.label}")
            at_v, xc = H.iso(call.at), {"call": call.label, "at_basis": call.at_basis}
            if call.source_at():
                xc["at_source"] = call.source_at()
            if f.get("endpoint") and call.endpoint and f["endpoint"] != call.endpoint:
                ref.add("endpoint", f"passes.{pid}.endpoint: hand-entered {f['endpoint']!r} but {call.label} was "
                                    f"answered by {call.endpoint}")
            ep_v = call.endpoint if call.endpoint and call.endpoint != ev_ep.get(f.get("evaluator")) else None
        elif f.get("at"):
            n = line_in(inputs_path, f.get("at"), "at")
            if n:
                xc = {"at_source": f"{rel_inputs}:{n}"}
        for dim in dims_read:
            c = {"dimension": dim, "evaluator": f.get("evaluator"), "run": f.get("run", 1),
                 "batch": f.get("batch"), "at": ts(at_v, f"checks[{pid}/{dim}].at", gaps),
                 "outcome": None, "score": None,
                 "failureCondition": (f.get("failureCondition") or {}).get(dim) or fail_cond.get(dim),
                 "evidence": None, "unobserved": None}
            if ep_v:
                c["endpoint"] = ep_v
            x = {"pass_id": pid, **xc}
            if x.get("at_source"):
                xp["sources"][f"checks[{pid}/{dim}].at"] = x["at_source"]
            if f.get("evaluator") not in ev_ids:
                gaps.add(f"checks[{pid}/{dim}].evaluator", f"{f.get('evaluator')!r} is not a listed evaluator")
            if not c["batch"]:
                gaps.add(f"checks[{pid}/{dim}].batch", "not recorded")
            if not c["failureCondition"]:
                gaps.add(f"checks[{pid}/{dim}].failureCondition", "not declared on the bar dimension or the pass")
            sc = scores.get(dim)
            explicit = (f.get("outcomes") or {}).get(dim)
            void = p.get("status") not in (None, "filed") or (sc is None and explicit is None)
            if void:
                c["outcome"] = "unobserved"
                c["unobserved"] = {"channel": p.get("channel") or p.get("provider") or "unrecorded",
                                   "reason": p.get("void_cause") or (f.get("unobserved_reason") or {}).get(dim)
                                   or f"pass {pid} filed no score for {dim} (status {p.get('status')!r})"}
            else:
                scale = scales.get(dim)
                if isinstance(scale, dict) and isinstance(sc, (int, float)) and "threshold" in scale:
                    c["score"] = sc
                    c["outcome"] = "conforms" if sc >= scale["threshold"] else "does_not_conform"   # CL1-17
                    if explicit and explicit != c["outcome"]:
                        gaps.add(f"checks[{pid}/{dim}].outcome", f"the inputs say {explicit!r} but score {sc} "
                                 f"against threshold {scale['threshold']} reads {c['outcome']!r}; CL1-17 decides", False)
                elif explicit in ("conforms", "does_not_conform"):
                    c["outcome"] = explicit
                    if sc is not None:
                        x["score"] = sc
                        x["score_note"] = "Plumbline score; the bar declares no custody scale for this dimension"
                else:
                    gaps.add(f"checks[{pid}/{dim}].outcome", "a score with no bar scale, and no recorded outcome")
                ev_name = (f.get("evidence") or {}).get(dim)
                if ev_name and (ev_dir / ev_name).is_file():
                    c["evidence"] = {"name": ev_name, "sha256": file_digest(ev_dir / ev_name)}
                    qs = [q for q in quotes.get((pid, s_key(pl_name, dim)), []) if q]
                    if qs:
                        text = (ev_dir / ev_name).read_text(encoding="utf-8", errors="replace")
                        x["quotes"] = [{"quote": q, "inEvidenceFile": q in text} for q in qs]
                else:
                    gaps.add(f"checks[{pid}/{dim}].evidence", "no evaluator evidence file named" if not ev_name
                             else f"evidence file {ev_name!r} not under {ev_dir.relative_to(job)}")
            c["x-plumbline"] = x
            checks.append(c)
    for i, c in enumerate(ci.get("checks") or []):     # a readings job: checks recorded directly
        c = dict(c)
        en = c.pop("evidence_file", None)
        if en:
            c["evidence"] = {"name": en, "sha256": file_digest(ev_dir / en)} if (ev_dir / en).is_file() else None
            if c["evidence"] is None:
                gaps.add(f"checks[+{i}].evidence", f"evidence file {en!r} missing")
        if c.get("at"):
            n = line_in(inputs_path, c.get("at"), "at")
            if n:
                xc = c.get("x-plumbline")
                if not isinstance(xc, dict):
                    xc = {}
                xc["at_source"] = f"{rel_inputs}:{n}"
                c["x-plumbline"] = xc
                xp["sources"][f"checks[+{i}].at"] = f"{rel_inputs}:{n}"
        checks.append(c)
    # d1: every called check carries its OWN at_source. One pass's bar dimensions are read by that pass's one
    # evaluator call, so the call's time line would otherwise repeat for each dimension. The file:line that carries
    # the time stays first; the check it sources is named after it, so no two called checks collide.
    shared_sources: dict[str, int] = {}
    for c in checks:
        x = c.get("x-plumbline") or {}
        if x.get("call") and x.get("at_source"):
            shared_sources[x["at_source"]] = shared_sources.get(x["at_source"], 0) + 1
    for c in checks:
        x = c.get("x-plumbline") or {}
        s = x.get("at_source")
        if not (x.get("call") and s and shared_sources.get(s, 0) > 1):
            continue
        own = f"{s} ({x.get('pass_id') or 'check'}/{c.get('dimension') or '?'})"
        x["at_source"] = own
        key = f"checks[{x.get('pass_id')}/{c.get('dimension')}].at"
        if key in xp["sources"]:
            xp["sources"][key] = own
    if not checks:
        gaps.add("checks", "no filed pass and no recorded check")
    for d in dims:
        if d["id"] and not any(c.get("dimension") == d["id"] for c in checks):
            gaps.add("checks", f"bar dimension {d['id']} has no check (custody CL1-7: every dimension is checked)")

    # ---- controls: a clean and a planted case per evaluator per batch, by case digest ----
    controls = []
    for i, k in enumerate(ci.get("controls") or []):
        ctl = {"id": k.get("id"), "batch": k.get("batch"), "evaluator": k.get("evaluator"),
               "case": digest_of(job, k.get("case_file"), f"controls[{i}].case", gaps),
               "expected": k.get("expected"), "outcome": k.get("outcome")}
        if "dimension" in k:
            ctl["dimension"] = k["dimension"]
        xk = {}
        if k.get("evidence_file"):
            p = job / k["evidence_file"]
            xk["evidence"] = {"name": k["evidence_file"], "sha256": file_digest(p)} if p.is_file() else None
        # A typed control time is a hand time whether or not a call is linked (T2c); a linked call's time is
        # cross-checked and is the time the record carries.
        if k.get("at"):
            mark(f"controls[{k.get('id')}].at", rel_inputs, line_in(inputs_path, k.get("at"), "at"), "inputs-no-ledger")
        call = link_call(ev_calls, k.get("evaluator"), k.get("call"), f"eval_{str(k.get('id') or '').lower()}",
                         f"controls[{k.get('id')}]", ref)
        if call is not None:
            H.cross_check(ref, f"controls[{k.get('id')}].at", k.get("at"), call.at, f"harness log {call.label}")
            xk.update({"call": call.label, "at": H.iso(call.at), "at_basis": call.at_basis})
            if call.source_at():
                xk["at_source"] = call.source_at()
            if call.endpoint and call.endpoint != ev_ep.get(k.get("evaluator")):
                xk["endpoint"] = call.endpoint
        elif k.get("at"):
            xk["at"] = k["at"]
            n = line_in(inputs_path, k["at"], "at")
            if n:
                xk["at_source"] = f"{rel_inputs}:{n}"
        if xk:
            ctl["x-plumbline"] = xk
            if xk.get("at_source"):
                xp["sources"][f"controls[{k.get('id')}].at"] = xk["at_source"]
        controls.append(ctl)
    have = {(k["evaluator"], k["batch"], k["expected"]) for k in controls}
    for c in checks:
        if c.get("outcome") in ("conforms", "does_not_conform"):
            for exp in ("conforms", "does_not_conform"):
                if (c["evaluator"], c["batch"], exp) not in have:
                    gaps.add("controls", f"evaluator {c['evaluator']} batch {c['batch']} has no control expecting {exp}")
                    have.add((c["evaluator"], c["batch"], exp))
    if not controls:
        gaps.add("controls", "no control recorded")

    # ---- violations: Plumbline's, each with its one rule-4 locator under x- ----
    # A §5 violation names no dimension (corpus §5 shape); the bar dimension it breaks is the Orchestrator's
    # ledger fact (inputs `violations.<id>.dimension`), never guessed from the scores.
    vfacts = ci.get("violations") or {}
    violations = []
    for v in (rec or {}).get("violations") or []:
        vf = vfacts.get(str(v.get("id"))) or {}
        d = vf.get("dimension") or pl_name.get(v.get("dimension"), v.get("dimension"))
        xv = {"locator": v.get("class"), "id": v.get("id")}
        if v.get("class") not in LOCATORS:
            gaps.add(f"violations[{v.get('id')}].locator", f"{v.get('class')!r} is not one of rule 4's four locators")
        r = vf.get("remedy")
        if r:
            src = ev_dir / str(r.get("evidence_file", ""))
            if r.get("evidence_file") and src.is_file() and r.get("text") and r["text"] in src.read_text(encoding="utf-8", errors="replace"):
                xv["remedy"] = {"text": r["text"], "evidence": {"name": r["evidence_file"], "sha256": file_digest(src)}}
            else:
                gaps.add(f"violations[{v.get('id')}].remedy", "a remedy was offered but is not verbatim in a named "
                         "evaluator evidence file: dropped (the emitter never writes a remedy)", False)
        if not d:
            gaps.add(f"violations[{v.get('id')}].dimension", "the §5 violation names no dimension and the custody "
                     "inputs do not say which bar dimension it breaks")
        violations.append({"dimension": d, "description": v.get("observation") or "", "x-plumbline": xv})
    if not rec:
        for vid, vf in sorted(vfacts.items()):
            if vf.get("locator"):
                violations.append({"dimension": vf.get("dimension"), "description": vf.get("description", ""),
                                   "x-plumbline": {"locator": vf["locator"], "id": vid}})
                if vf["locator"] not in LOCATORS:
                    gaps.add(f"violations[{vid}].locator", f"{vf['locator']!r} is not one of rule 4's four locators")
    nonconf = {c["dimension"] for c in checks if c.get("outcome") == "does_not_conform"}
    for d in sorted(nonconf - {v["dimension"] for v in violations}):
        gaps.add("violations", f"dimension {d} does not conform and Plumbline filed no violation naming it")

    # ---- external (harness logs), retention, disposition ----
    external = []
    for i, e in enumerate(ci.get("external") or []):
        p = ev_dir / str(e.get("evidence_file", ""))
        external.append({"requirement": e.get("requirement", "CL1-15"), "subject": e.get("subject"),
                         "evidence": {"name": e["evidence_file"], "sha256": file_digest(p)} if e.get("evidence_file") and p.is_file() else None,
                         "readBy": e.get("readBy")})
        if external[-1]["evidence"] is None:
            gaps.add(f"external[{i}].evidence", "harness log not found under the evidence folder")
    for e in evs:
        if e["kind"] == "model" and not any(x.get("subject") == e["id"] for x in external):
            gaps.add("external", f"no harness log (CL1-15) for model evaluator {e['id']}", False)
    ret = ci.get("retention")
    if not ret:
        gaps.add("retention", "where the record and its evidence are kept is not recorded")
    state = packet.get("disposition_state")
    if state not in DISPOSITIONS:
        gaps.add("disposition.state", f"packet disposition_state is {state!r}: the close has not recorded one")
        state = None
    dsp = ci.get("disposition") or {}
    at = dsp.get("at")
    live = ev_log.get("dispose") if have_inputs else None
    # The live `dispose` line is read to CHECK the record, never to supply its state: the Owner ruled the
    # record's disposition.state is packet.disposition_state (docstring, lines 14-15), so the line's own `state`
    # must agree with that value or the disagreement is refused by name. Silently dropping the line would hide
    # that Plumbline's own live event log contradicts the record it is holding.
    if live is not None and "state" in live and live.get("state") is not None:
        line_state = live["state"]
        if not (isinstance(line_state, str) and line_state in DISPOSITIONS):
            gaps.add("disposition.state", f"the dispose line's state {line_state!r} is a shape the emitter does "
                     f"not read (not a known disposition value), so it cannot be checked against the record's "
                     f"{state!r} ({LEDGER_REL}:{live.get('_line')})")
        elif state is not None and line_state != state:
            gaps.add("disposition.state", f"the dispose line says {line_state!r} but the record would say "
                     f"{state!r} (packet.json disposition_state); the line is not dropped "
                     f"({LEDGER_REL}:{live.get('_line')})")
    # `dispose --decided-at T` writes T into custody.json (`disposition.at`) and keeps the tool clock in the
    # line's `at` (INTERFACE 1; kit/custody_ledger.py). The value to compare with — and the value the record's
    # disposition.at gets — is the line's decided_at; a line with no decided_at (the base form) uses `at`.
    # F1b: the record's disposition.at = decided_at. A real disagreement still refuses (kind `time`).
    live_at = (live.get("decided_at") or live.get("at")) if live else None
    if live and at and (live_at != at or (live.get("by") and dsp.get("by") and live.get("by") != dsp.get("by"))):
        ref.add("time", f"disposition: the ledger says {dsp.get('by')!r} at {at!r} but {LEDGER_REL} "
                        f"logged {live.get('by')!r} at {live_at!r}")
    if live and not at and live_at:
        at = live_at
    if live:
        src = writer_source(live)
        if src:
            mark("disposition.at", LEDGER_REL, live.get("_line"), src)
    elif dsp.get("at"):
        mark("disposition.at", rel_inputs, line_in(inputs_path, dsp.get("at"), "at"), "inputs-no-ledger")
    if not at:
        at = H.iso(now)
        xp["disposition_at_source"] = "emission time: no disposition time recorded (custody tools/make_record.py convention)"
    elif live:
        xp["disposition_at_source"] = "logged live (inputs/custody-events.jsonl)"
        xp["sources"]["disposition.at"] = f"{LEDGER_REL}:{live['_line']}"
    else:
        n = line_in(inputs_path, at, "at")
        if n:
            xp["sources"]["disposition.at"] = f"{rel_inputs}:{n}"
    disposition = {"state": state, "by": dsp.get("by"), "at": ts(at, "disposition.at", gaps),
                   "acknowledgesUnobserved": list(dsp.get("acknowledgesUnobserved") or [])}
    if not dsp.get("by"):
        gaps.add("disposition.by", "the approver is not named in the custody inputs")

    level = ci.get("levelClaimed") or "CL1"
    pred = {
        "specVersion": version, "levelClaimed": level, "bar": bar, "maker": maker,
        "startedAt": ts(mk.get("startedAt") or ci.get("startedAt"), "startedAt", gaps),
        "producedAt": ts(mk.get("producedAt") or ci.get("producedAt"), "producedAt", gaps),
        "instrument": instrument, "evaluators": evs, "checks": checks, "controls": controls,
        "disagreements": list(ci.get("disagreements") or []), "violations": violations,
        "separationGaps": sep, "retention": ret, "external": external, "disposition": disposition,
    }
    if ci.get("spread") is not None or level in ("CL2", "CL3"):
        pred["spread"] = list(ci.get("spread") or [])
    if ci.get("demonstrations") is not None or level == "CL3":
        pred["demonstrations"] = list(ci.get("demonstrations") or [])
    if ci.get("readsBeforeFreeze") is not None:
        pred["readsBeforeFreeze"] = list(ci["readsBeforeFreeze"])
    if xp.get("terminal_state") not in TERMINALS:
        gaps.add("x-plumbline.terminal_state", f"packet terminal_state is {xp.get('terminal_state')!r}")
    if xp.get("verdict") is not None and xp["verdict"] not in VERDICTS:
        gaps.add("x-plumbline.verdict", f"{xp['verdict']!r} is not a Plumbline verdict")
    xp["emitter"] = {"name": "kit/emit_custody.py", "kit_revision": (rev.get("commit") or "")[:7] or None,
                     "commit": rev.get("commit"), "tree": rev.get("tree"), "dirty": rev.get("dirty"),
                     "statedRevision": rev.get("stated")}
    xp["time_tolerance_s"] = H.TOLERANCE_S
    xp["times"] = {"startedAt": "harness log" if mk.get("startedAt") else "hand-entered",
                   "producedAt": "harness log" if mk.get("producedAt") else "hand-entered"}
    # every time field -> the file:line that carries it (custody N3); `sources` holds only file:line strings
    tsrc = time_sources(pred, xp)
    xp["timeSources"] = tsrc
    xp["time_sources"] = dict(tsrc)
    check_order(pred, packet, ci, now, ref)
    xp["emittedAt"] = H.iso(now)
    # ---- the versioned block, hand times, the F1 arrays, spend and the inputs' own x-plumbline ----
    xp["schema"] = "plumbline/x-plumbline/v1"
    if version_block:
        xp["spec_version"] = version_block
    xp["hand_times"] = [hand[k] for k in hand]
    if hand and allow_hand:
        xp["allowances"] = {"hand_times": {"switch": "--allow-hand-times", "writer": emitter_stamp(),
                                           "at": H.iso(now)}}
    if hand and not allow_hand:
        for e in hand.values():
            ref.add("hand-time", f"{e['field']} {e['file']}:{e['line']} ({e['source']})")
    xp["generations"] = ledger_array(lines, "generation")
    xp["evaluations"] = ledger_array(lines, "evaluation")
    xp["relays"] = ledger_array(lines, "relay")
    xp["amendments"] = ledger_array(lines, "amendment")
    xp["spend"] = spend_block(lines, all_calls)
    inp_x = ci.get("x-plumbline")
    if isinstance(inp_x, dict):
        xp["inputs"] = json.loads(json.dumps(inp_x))
    xp["gaps"] = gaps.rows
    pred["x-plumbline"] = xp
    return {"_type": STATEMENT, "subject": subject, "predicateType": PREDICATE_TYPE, "predicate": pred}, gaps, notes


def find_log(job: Path, ev_dir: Path, rel: str | None, pattern: str | None) -> Path | None:
    if rel:
        for base in (ev_dir, job):
            if (base / rel).is_file():
                return base / rel
        return None
    hits = sorted(ev_dir.glob(pattern)) if pattern and ev_dir.is_dir() else []
    return hits[0] if len(hits) == 1 else None


def pin_for(ci: dict, ev_log: dict, seat: str, ref: H.Refusals) -> dict | None:
    """The seat's declared provider pin (inputs routing.<seat>), which must be the one logged live."""
    pin = (ci.get("routing") or {}).get(seat)
    live = ev_log["pin"].get(seat)
    if not pin and not live:
        return None
    if not live:
        ref.add("endpoint", f"routing.{seat}: a provider pin is in the custody inputs but not in "
                            f"{LEDGER_REL}; a pin is declared with custody_ledger.py pin so its time "
                            f"is stamped, not typed")
        return None
    if not pin:
        pin = {k: live.get(k) for k in PIN_KEYS} | {"declaredAt": live.get("at")}
    for k in PIN_KEYS:
        if str(pin.get(k)) != str(live.get(k)):
            ref.add("endpoint", f"routing.{seat}.{k}: the inputs say {pin.get(k)!r} but the pin logged in "
                                f"{LEDGER_REL} says {live.get(k)!r}")
    if pin.get("declaredAt") != live.get("at"):
        ref.add("time", f"routing.{seat}.declaredAt: the inputs say {pin.get('declaredAt')!r} but the pin was "
                        f"logged at {live.get('at')!r}")
    host = str(pin.get("host") or "")
    if not H.HOST.match(host) or host in H.AGGREGATORS:
        ref.add("endpoint", f"routing.{seat}.host {host!r} is not an upstream provider's host name")
    return dict(pin, declaredAt=live.get("at"))


PIN_KEYS = ("via", "provider", "slug", "host")


def check_pin_order(pin: dict | None, calls, who: str, ref: H.Refusals) -> None:
    if not pin or not calls:
        return
    first = min(calls, key=lambda c: c.started)
    at = H.parse_ts(pin.get("declaredAt"))
    if at is None or at > first.started:
        ref.add("order", f"{who}: provider pin declared at {pin.get('declaredAt')!r}, after the seat's first call "
                         f"{first.label} ({H.iso(first.started)}); a pin chosen after the calls is not a pin")


def routing_x(calls, pin: dict | None, seat: str, gaps: Gaps) -> dict | None:
    """What each aggregator call asked OpenRouter for; a request that did not ask for the pin is a hard gap."""
    agg = [c for c in calls if c.host in H.AGGREGATORS]
    if not agg or not pin:
        return None
    reqs, bad = {}, {}
    for c in agg:
        key = json.dumps(c.routing, sort_keys=True)
        reqs.setdefault(key, []).append(c.label)
        probs = H.routing_problems(c.routing, pin)
        if probs:
            bad[c.label] = probs
    for label, probs in bad.items():
        gaps.add(f"routing.{seat}.request", f"{label} did not ask OpenRouter for the pin: " + "; ".join(probs)
                 + ". The served provider is still read from the log, but nothing in the request kept the prompt "
                   "on one zero-retention provider. Re-emitting cannot fix this; the run's own request did it.")
    return {"pin": {k: pin.get(k) for k in (*PIN_KEYS, "declaredAt")},
            "requests": [{"provider": json.loads(k), "calls": v} for k, v in reqs.items()],
            "request_ok": not bad}


def annotate(calls, who: str, identifier, ref: H.Refusals, pin: dict | None = None) -> None:
    for c in calls:
        c.endpoint, c.route = H.endpoint_of(c, ref, who, pin)
        if identifier and not H.model_matches(c.model, identifier):
            ref.add("model", f"{who}: {c.label} ran model {c.model!r}, not the recorded identifier {identifier!r}")


def route_x(log: Path, calls) -> dict:
    x = {"harness_log": log.name, "calls": [c.label for c in calls]}
    aggs = sorted({c.route.get("aggregator") for c in calls if c.route.get("aggregator")})
    if aggs:
        x["aggregator"] = aggs[0] if len(aggs) == 1 else aggs
        ups = sorted({str(c.route.get("upstream_provider")) for c in calls if c.route.get("upstream_provider")})
        x["upstream_provider"] = ups[0] if len(ups) == 1 else ups
        sl = sorted({str(c.route.get("provider_slug")) for c in calls if c.route.get("provider_slug")})
        if sl:
            x["provider_slug"] = sl[0] if len(sl) == 1 else sl
    bases = sorted({c.route.get("endpoint_basis") for c in calls if c.route.get("endpoint_basis")})
    if bases:
        x["endpoint_basis"] = bases[0] if len(bases) == 1 else bases
    return x


def maker_history(job: Path, ev_dir: Path, ci: dict, m: dict, ref: H.Refusals, pin: dict | None = None,
                  gaps: Gaps | None = None, hand: dict | None = None) -> dict:
    """startedAt / producedAt / endpoint for a model maker, read from its harness log."""
    log = find_log(job, ev_dir, m.get("harness_log"), "harness-maker*.log")
    if log is None:
        ref.add("time", f"maker: a model maker needs its harness log (maker.harness_log, or exactly one "
                        f"harness-maker*.log in the evidence folder); none {'at ' + repr(m['harness_log']) if m.get('harness_log') else 'found'}, "
                        f"so startedAt, producedAt and the endpoint have no source")
        return {}
    # The emitter never writes its inputs (T7): the log is read as it is. Every call the logger did not stamp is
    # a hand time (T7b), whether or not it is the first or the last.
    log_calls = H.read_log(log, ref, "maker")
    flag_calls(log_calls, hand)
    calls = log_calls
    if m.get("calls"):
        calls = [c for c in calls if c.name in m["calls"]]
    calls = [c for c in calls if c.at]
    if not calls:
        return {}
    if gaps is not None and any("sent_at" in c.raw or "received_at" in c.raw for c in calls):
        for c in calls:
            missing = [k for k in ("sent_at", "received_at") if not c.raw.get(k)]
            if missing:
                gaps.add(f"maker.{c.label}", f"the Maker harness call {c.label} carries no "
                          f"{' or '.join(missing)}; startedAt/producedAt cannot be read from the log")
    annotate(calls, "maker", (m.get("model") or {}).get("identifier"), ref, pin)
    check_pin_order(pin, calls, "maker", ref)
    first = min(calls, key=lambda c: c.started)
    last = max(calls, key=lambda c: c.at)
    started, produced = first.started, last.at
    H.cross_check(ref, "startedAt", ci.get("startedAt"), started, f"harness log {first.label}")
    H.cross_check(ref, "producedAt", ci.get("producedAt"), produced, f"harness log {last.label}")
    out = {"startedAt": H.iso(started), "producedAt": H.iso(produced), "endpoint": last.endpoint,
           "_calls": calls,
           "x": {**route_x(log, calls),
                 "startedAt_basis": (f"{first.label} sent_at" if first.sent else
                                     (f"{first.label} response created" if first.created else
                                      f"{first.label} response Date header")),
                 "producedAt_basis": (f"{last.label} received_at" if last.received else
                                      f"{last.label} {last.at_basis}"),
                 "startedAt_source": first.source_started(),
                 "producedAt_source": last.source_at()}}
    rx = routing_x(calls, pin, "maker", gaps if gaps is not None else Gaps())
    if rx:
        out["x"]["routing"] = rx
    hand_ep = (m.get("model") or {}).get("endpoint")
    if hand_ep and last.endpoint and hand_ep != last.endpoint:
        ref.add("endpoint", f"maker.model.endpoint: hand-entered {hand_ep!r} but {last.label} "
                            + (f"went to {last.host} and was answered upstream by {last.route.get('upstream_provider')!r} "
                               f"({last.endpoint})" if last.route.get("aggregator") else f"was answered by {last.endpoint}"))
    return out


def evaluator_history(job: Path, ev_dir: Path, ci: dict, e: dict, ref: H.Refusals, pin: dict | None = None,
                      gaps: Gaps | None = None, hand: dict | None = None) -> dict:
    who = f"evaluator {e.get('id')}"
    rel = e.get("harness_log") or next((x.get("evidence_file") for x in ci.get("external") or []
                                        if x.get("subject") == e.get("id")), None)
    log = find_log(job, ev_dir, rel, None)
    if log is None:
        ref.add("time", f"{who}: a model evaluator needs its harness log (evaluators[].harness_log, or the CL1-15 "
                        f"external entry for it); {'not found: ' + repr(rel) if rel else 'none named'}, so its check "
                        f"times and endpoint have no source")
        return {}
    # The emitter never writes its inputs (T7): the log is read as it is. Every call counts for T7b, not only the
    # call a check is linked to.
    log_calls = H.read_log(log, ref, who)
    flag_calls(log_calls, hand)
    # A model evaluator's CHECK time must come from an instant its own harness log records: the logger's
    # `received_at`, or the server-set response `Date` header. A call with neither leaves only the response
    # `created` epoch, which the logger never stamped. `--allow-hand-times` admits a time a person typed; it cannot
    # make a machine's unstamped clock a person's, so every such call is refused BY ID and nothing is written (T7b).
    for c in log_calls:
        if c.received is None and c.date is None:
            ref.add("check-time", f"{who}: {c.label} carries no logger `received_at` and no response `Date` header, "
                                  f"so its check time would be the response `created` epoch the logger never "
                                  f"stamped. --allow-hand-times admits a time a person typed; it cannot make a "
                                  f"machine's clock a person's, so this check time is refused.")
    calls = [c for c in log_calls if c.at]
    if not calls:
        return {}
    annotate(calls, who, (e.get("model") or {}).get("identifier"), ref, pin)
    check_pin_order(pin, calls, who, ref)
    first = min(calls, key=lambda c: c.at)
    hand_ep = (e.get("model") or {}).get("endpoint")
    if hand_ep and first.endpoint and hand_ep != first.endpoint:
        ref.add("endpoint", f"evaluators[{e.get('id')}].model.endpoint: hand-entered {hand_ep!r} but {first.label} "
                            + (f"went to {first.host} and was answered upstream by "
                               f"{first.route.get('upstream_provider')!r} ({first.endpoint})"
                               if first.route.get("aggregator") else f"was answered by {first.endpoint}"))
    named = {}
    for c in calls:
        named.setdefault(c.name or str(c.i), c)
    x = route_x(log, calls)
    rx = routing_x(calls, pin, str(e.get("id")), gaps if gaps is not None else Gaps())
    if rx:
        x["routing"] = rx
    return {"calls": named, "endpoint": first.endpoint, "x": x}


def link_call(ev_calls: dict, ev_id, named, default, where: str, ref: H.Refusals):
    """The harness call a check or control came from. Only model evaluators have one."""
    if ev_id not in ev_calls:
        return None
    calls = ev_calls[ev_id]
    if not calls:
        return None                                          # the log itself was already refused
    name = named or (default if default in calls else None)
    if name is None and not named and len(calls) == 1:
        name = next(iter(calls))
    if name not in calls:
        ref.add("time", f"{where}: no harness call of evaluator {ev_id} is linked to it "
                        f"({'call ' + repr(named) + ' is not in the log' if named else 'set `call` to one of ' + ', '.join(sorted(calls))}); "
                        f"its time cannot be read from the log")
        return None
    return calls[name]


def time_sources(pred: dict, xp: dict) -> dict:
    """Every time field the record carries -> the `file:line` that carries it (custody N3).

    `x-plumbline.sources` holds only `file:line` strings; this copies it and adds the per-check, per-control
    and per-approval entries under their index keys, so a reader can look a field up by either name."""
    out = {k: v for k, v in (xp.get("sources") or {}).items() if isinstance(v, str) and v}
    if out.get("bar.frozenAt"):
        out.setdefault("frozenAt", out["bar.frozenAt"])
    bar = pred.get("bar") or {}
    for i, a in enumerate(bar.get("approvals") or []):
        s = (a.get("x-plumbline") or {}).get("at_source")
        if s:
            out[f"bar.approvals[{i}].at"] = s
            out[f"approvals[{i}].at"] = s
    for i, c in enumerate(pred.get("checks") or []):
        s = (c.get("x-plumbline") or {}).get("at_source")
        if s:
            out[f"checks[{i}].at"] = s
    for i, k in enumerate(pred.get("controls") or []):
        s = (k.get("x-plumbline") or {}).get("at_source")
        if s:
            out[f"controls[{i}].at"] = s
    return out


def check_order(pred: dict, packet: dict, ci: dict, now: datetime, ref: H.Refusals) -> None:
    """The record's events in the order they happened, none after the close or the emission."""
    P = H.parse_ts
    tol = timedelta(seconds=H.TOLERANCE_S)
    bar = pred.get("bar") or {}
    F, S, Pd = P(bar.get("frozenAt")), P(pred.get("startedAt")), P(pred.get("producedAt"))
    checks = [(f"checks[{(c.get('x-plumbline') or {}).get('pass_id', '?')}/{c.get('dimension')}].at", P(c.get("at")),
               bool((c.get("x-plumbline") or {}).get("call"))) for c in pred.get("checks") or []]
    ctls = [(f"controls[{k.get('id')}].at", P((k.get("x-plumbline") or {}).get("at")),
             bool((k.get("x-plumbline") or {}).get("call"))) for k in pred.get("controls") or []]
    apprs = [(f"bar.approvals[{i}].at ({a.get('role')})", P(a.get("at"))) for i, a in enumerate(bar.get("approvals") or [])]
    D = P((pred.get("disposition") or {}).get("at"))
    from_log = (pred.get("x-plumbline") or {}).get("times", {})
    events = [("bar.frozenAt", F, False), *[(n, t, False) for n, t in apprs],
              ("startedAt", S, from_log.get("startedAt") == "harness log"),
              ("producedAt", Pd, from_log.get("producedAt") == "harness log"), *checks, *ctls,
              ("disposition.at", D, False)]

    def before(an, a, bn, b, strict=False):
        if a and b and (a >= b if strict else a > b):
            ref.add("order", f"{an} {H.iso(a)} is {'not before' if strict else 'after'} {bn} {H.iso(b)}")

    before("bar.frozenAt", F, "startedAt", S, strict=True)
    for n, t in apprs:
        before("bar.frozenAt", F, n, t)
        before(n, t, "startedAt (the maker's first call)", S)
    before("startedAt", S, "producedAt", Pd)
    for n, t, _ in checks:
        before("producedAt", Pd, n, t)
    last = max([t for _, t, _ in checks if t] or [None], key=lambda t: t or datetime.min.replace(tzinfo=timezone.utc))
    if last:
        before("the last check", last, "disposition.at", D)
    close = P(((packet.get("close") or {}) if isinstance(packet.get("close"), dict) else {}).get("date"))
    for n, t, logged in events:
        if not t:
            continue
        if n != "disposition.at" and close and t > close + (tol if logged else timedelta(0)):
            ref.add("order", f"{n} {H.iso(t)} is after the job's close (packet close.date {H.iso(close)})")
        if t > now + (tol if logged else timedelta(0)):
            ref.add("after-emit", f"{n} {H.iso(t)} is after this record's emission at {H.iso(now)}: a record cannot "
                                  f"report an event that had not happened")


def s_key(pl_name: dict, dim: str) -> str:
    """The Plumbline dimension name a bar dimension id was mapped from (quotes are keyed by it)."""
    for k, v in pl_name.items():
        if v == dim:
            return k
    return dim


def _now_from_env():
    """The clock ``$PLUMBLINE_EMIT_NOW`` pins, or None when it is unset.

    Unset, ``build()`` keeps the wall clock. Set, both a seam run and its twin
    can be given the same instant, so a second boundary is not a record diff.
    A set value that is not an ISO timestamp is a refusal, not a silent fallback.
    """
    raw = (os.environ.get("PLUMBLINE_EMIT_NOW") or "").strip()
    if not raw:
        return None
    text = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"PLUMBLINE_EMIT_NOW is not an ISO timestamp ({raw!r})") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Emit a custody/v1 record for a job at a terminal state.")
    ap.add_argument("--job-dir", required=True)
    ap.add_argument("--inputs", help="custody inputs (default: <job>/inputs/custody.json)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--out", help="output file (default: <job>/custody/record.custody.json)")
    g.add_argument("--out-dir", help="write <out-dir>/<job_id>.custody.json")
    ap.add_argument("--print-only", action="store_true")
    ap.add_argument("--allow-hand-times", action="store_true",
                    help="write the record with the hand-entered times listed in x-plumbline.hand_times[] and the "
                         "allowance recorded (default: refuse them, exit 3)")
    ap.add_argument("--spec-version", help="the custody spec version (X.Y.Z) the record attests when the job "
                                           "names no custody document (inputs/custody.json: custody_spec); the "
                                           "record says so under x-plumbline.spec_version.origin")
    ap.add_argument("--expect-revision", help="the emitter revision (commit or tree, >= 7 hex) this record must "
                                              "be written by; also $PLUMBLINE_EXPECT_REVISION")
    a = ap.parse_args(argv)
    job = Path(a.job_dir).expanduser().resolve()
    if not (job / "packet.json").is_file():
        print(f"REFUSED: {job} has no packet.json — custody is written for a job, and a job is its packet.")
        return 2
    try:
        packet = load(job / "packet.json")
    except Exception as exc:
        print(f"REFUSED: packet.json unreadable ({exc})"); return 2
    if packet.get("terminal_state") not in TERMINALS:
        print(f"REFUSED: the packet's terminal_state is {packet.get('terminal_state')!r}, not one of {TERMINALS}. "
              f"A custody record is written when a job ENDS; close it with --terminal-state first.")
        return 2
    inputs = Path(a.inputs).expanduser() if a.inputs else job / "inputs" / "custody.json"
    ref = H.Refusals()
    try:
        pinned = _now_from_env()
    except ValueError as exc:
        print(f"REFUSED: {exc}")
        return 2
    try:
        record, gaps, _ = build(job, inputs, ref, now=pinned, expect=a.expect_revision,
                                allow_hand=a.allow_hand_times, spec_version=a.spec_version)
    except (ValueError, OSError) as exc:
        print(f"REFUSED: could not read the job's files ({exc})"); return 2
    if ref:
        print(f"REFUSED (history): {len(ref.rows)} fact(s) this record would misstate — nothing written"
              f"{' (the existing record is untouched)' if not a.print_only else ''}:")
        for kind, msg in ref.rows:
            print(f"  [{kind}] {msg}")
        print("  Fix the source (harness log, custody inputs, live event log, or the emitter checkout) and re-emit; "
              "see docs/custody-emission.md, 'Refusals'.")
        return 3
    text = json.dumps(record, indent=2, ensure_ascii=False) + "\n"
    if a.out:
        out = Path(a.out).expanduser()
    elif a.out_dir:
        out = Path(a.out_dir).expanduser() / f"{record['predicate']['x-plumbline']['job_id']}.custody.json"
    else:
        out = job / "custody" / "record.custody.json"
    if a.print_only:
        print(text[:1500]); print(f"(would write {out})")
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"custody: wrote {out}  sha256 {sha256(text.encode('utf-8')).hexdigest()}")
    xp = record["predicate"]["x-plumbline"]
    print(f"  terminal_state={xp.get('terminal_state')} · x-plumbline.verdict={xp.get('verdict')} · "
          f"disposition={record['predicate']['disposition']['state']} · levelClaimed={record['predicate']['levelClaimed']} · "
          f"{len(record['predicate']['checks'])} check(s), {len(record['predicate']['controls'])} control(s), "
          f"{len(record['predicate']['violations'])} violation(s)")
    for r in gaps.rows:
        print(f"  {'GAP ' if r['hard'] else 'note'} {r['field']}: {r['reason']}")
    if gaps.hard:
        print(f"  {len(gaps.hard)} hard gap(s), named in x-plumbline.gaps: a required field had no source (left "
              f"null/absent; fix the inputs and re-emit), or the run itself fell short (routing.*: re-emitting "
              f"cannot fix it). This record is not clean.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""A file bridge that lets the kit's loop() hold rounds with bot seats.

Usage (cwd = the repo loop() runs in; inputs come only from the environment loop() sets):
  python3 kit/seat_bridge.py maker [--poll S]       as the packet's maker.cmd
  python3 kit/seat_bridge.py evaluator [--poll S]   as the packet's evaluator.cmd

``--poll`` is a positive number of seconds between looks at the answer file (default 1.0).

Environment read:
  maker:      PLUMBLINE_FINDINGS (record_dir/findings-NN.json), PLUMBLINE_COST (record_dir/cost-NN-maker.json)
  evaluator:  PLUMBLINE_TURN (the turn JSON), PLUMBLINE_COST (record_dir/cost-NN-eval-I.json)
R is the directory of PLUMBLINE_COST (= record_dir). It must already exist.

Files written, all under R, each atomically (a temporary name in the same directory, then os.replace),
never under cwd:
  maker:      R/bridge/maker-request-NN.json, then R/aider-dispatch.json; an earlier turn's
              R/aider-exit.json is moved, bytes unchanged, to R/bridge/aider-exit-stale-NN[-k].json
  evaluator:  R/bridge/eval-request-NN-I.json
  both:       PLUMBLINE_COST as {"amount": cost_usd, "unit": "USD", ...}, only when the seat declared
              cost_usd as a finite number >= 0 that is not a bool; R/bridge/log.jsonl, one JSON line per event
Files read (the seat writes them by atomic rename): R/aider-exit.json (maker),
R/bridge/eval-reading-NN-I.json (evaluator).

maker blocks until R/aider-exit.json holds {"round": N, "request_sha256": <the request's>, "exit": <int>}
and exits 0 only if that exit is 0. evaluator blocks until the reading file's "bridge" object names this
round, run and request, then prints the reading's bytes to stdout and nothing else, and exits 0.
Bad input exits 2 with a one-line reason on stderr; a seat's non-zero exit makes maker exit 1.
The bridge sends nothing, makes no network or model call and starts no process or thread.
The interface is fixed by job 2026-11-13-kit-bridge, bar.md section 3; docs/SEAT-BRIDGE.md explains it.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import os
import re
import sys
import time

EXIT_FILE = "aider-exit.json"
DISPATCH_FILE = "aider-dispatch.json"
MAKER_COST = re.compile(r"cost-(\d+)-maker\.json")
EVAL_COST = re.compile(r"cost-(\d+)-eval-(\d+)\.json")


class Refused(Exception):
    """A bad input: the command exits 2 with this one-line reason."""


def _now() -> str:
    """ISO 8601 with the local UTC offset, to the second."""
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dumps(obj) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write(path: str, data: bytes) -> None:
    """Write ``data`` to ``path`` atomically: a temporary name in the same directory, then os.replace."""
    tmp = os.path.join(os.path.dirname(path), ".%s.%d.tmp" % (os.path.basename(path), os.getpid()))
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)  # only our own temporary file
        raise


def _log(rec: str, event: str, **fields) -> None:
    """Append one JSON line to R/bridge/log.jsonl. The append is a rewrite by atomic replace: loop()
    runs one command at a time per record_dir, so no two bridge processes share the log."""
    path = os.path.join(rec, "bridge", "log.jsonl")
    line = dict(fields, at=_now(), event=event, pid=os.getpid())
    try:
        with open(path, "rb") as fh:
            old = fh.read()
    except FileNotFoundError:
        old = b""
    if old and not old.endswith(b"\n"):
        old += b"\n"
    _write(path, old + (json.dumps(line, sort_keys=True) + "\n").encode("utf-8"))


def _int(value) -> bool:
    return type(value) is int


def _cost(value):
    """The seat's cost_usd if it is a finite number >= 0 and not a bool, else None. Never a default."""
    if type(value) in (int, float) and math.isfinite(value) and value >= 0:
        return value
    return None


def _env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value.strip():
        raise Refused("%s is not set" % name)
    return value


def _record_dir(cost_path: str) -> str:
    rec = os.path.dirname(os.path.abspath(cost_path))
    if not os.path.isdir(rec):
        raise Refused("the directory of PLUMBLINE_COST does not exist: %s" % rec)
    return rec


def _read_json(path: str):
    """(bytes, parsed object) of a file that holds a complete JSON object, else None (wait on it)."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
        body = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError):
        return None
    return (raw, body) if isinstance(body, dict) else None


def _write_cost(rec: str, cost_path: str, declared: dict, source: str, source_sha: str) -> None:
    """maker step 6 / evaluator step 4: write the cost file from the seat's own cost_usd, or nothing."""
    amount = _cost(declared.get("cost_usd")) if "cost_usd" in declared else None
    if amount is None:
        _log(rec, "cost_not_written", reason="no cost_usd, or not a finite number >= 0",
             declared=repr(declared.get("cost_usd", "<absent>")))
        return
    _write(cost_path, _dumps({"amount": amount, "unit": "USD", "source": source,
                              "source_sha256": source_sha, "written_at": _now()}))
    _log(rec, "cost_written", path=cost_path, amount=amount)


def _ignore_once(rec: str, seen: set, raw: bytes, event: str, why: str) -> None:
    """Log a record that does not end the wait, once per distinct content."""
    key = _sha(raw)
    if key not in seen:
        seen.add(key)
        _log(rec, event, reason=why, content_sha256=key)


def maker(poll: float) -> int:
    findings_path = _env("PLUMBLINE_FINDINGS")
    cost_path = _env("PLUMBLINE_COST")
    rec = _record_dir(cost_path)
    try:
        with open(findings_path, "rb") as fh:
            raw = fh.read()
        findings = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise Refused("PLUMBLINE_FINDINGS unreadable: %s" % exc)
    if not isinstance(findings, dict) or not _int(findings.get("round")):
        raise Refused("PLUMBLINE_FINDINGS has no integer round")
    number = findings["round"]
    named = MAKER_COST.fullmatch(os.path.basename(cost_path))
    if not named:
        raise Refused("PLUMBLINE_COST is not named cost-NN-maker.json: %s" % cost_path)
    if int(named.group(1)) != number:
        raise Refused("findings round %d disagrees with %s" % (number, os.path.basename(cost_path)))

    bridge = os.path.join(rec, "bridge")
    os.makedirs(bridge, exist_ok=True)
    _log(rec, "maker_start", round=number, findings=findings_path, poll=poll)
    exit_file = os.path.join(rec, EXIT_FILE)
    if os.path.lexists(exit_file):  # an earlier turn's record: keep its bytes, never delete it
        kept, k = os.path.join(bridge, "aider-exit-stale-%02d.json" % number), 1
        while os.path.lexists(kept):
            kept, k = os.path.join(bridge, "aider-exit-stale-%02d-%d.json" % (number, k)), k + 1
        os.rename(exit_file, kept)
        _log(rec, "stale_exit_kept", moved_to=kept)

    request_path = os.path.join(bridge, "maker-request-%02d.json" % number)
    request = _dumps({"kind": "maker_request", "round": number, "findings": findings,
                      "findings_sha256": _sha(raw), "cwd": os.path.realpath(os.getcwd()),
                      "exit_file": exit_file, "written_at": _now()})
    request_sha = _sha(request)
    _write(request_path, request)
    _log(rec, "request_written", path=request_path, sha256=request_sha)
    _write(os.path.join(rec, DISPATCH_FILE), _dumps({"round": number, "request": request_path,
                                                     "request_sha256": request_sha, "exit_file": exit_file}))
    _log(rec, "dispatch_written", path=os.path.join(rec, DISPATCH_FILE), round=number)

    seen: set = set()
    while True:
        got = _read_json(exit_file)
        if got is not None:
            body_raw, body = got
            if body.get("round") == number and _int(body.get("round")) \
                    and body.get("request_sha256") == request_sha and _int(body.get("exit")):
                break
            _ignore_once(rec, seen, body_raw, "exit_record_ignored",
                         "names another round or request, or has no integer exit")
        time.sleep(poll)
    _log(rec, "exit_record_accepted", exit=body["exit"], sha256=_sha(body_raw))
    _write_cost(rec, cost_path, body, exit_file, _sha(body_raw))
    code = 0 if body["exit"] == 0 else 1
    _log(rec, "maker_done", seat_exit=body["exit"], exit=code)
    return code


def evaluator(poll: float) -> int:
    turn_text = _env("PLUMBLINE_TURN")
    cost_path = _env("PLUMBLINE_COST")
    rec = _record_dir(cost_path)
    try:
        turn = json.loads(turn_text)
    except ValueError as exc:
        raise Refused("PLUMBLINE_TURN is not JSON: %s" % exc)
    if not isinstance(turn, dict) or not _int(turn.get("round")):
        raise Refused("PLUMBLINE_TURN has no integer round")
    number = turn["round"]
    named = EVAL_COST.fullmatch(os.path.basename(cost_path))
    if not named:
        raise Refused("PLUMBLINE_COST is not named cost-NN-eval-I.json: %s" % cost_path)
    if int(named.group(1)) != number:
        raise Refused("turn round %d disagrees with %s" % (number, os.path.basename(cost_path)))
    run = int(named.group(2))

    bridge = os.path.join(rec, "bridge")
    os.makedirs(bridge, exist_ok=True)
    _log(rec, "evaluator_start", round=number, run=run, poll=poll)
    request_path = os.path.join(bridge, "eval-request-%02d-%d.json" % (number, run))
    reading_file = os.path.join(bridge, "eval-reading-%02d-%d.json" % (number, run))
    request = _dumps({"kind": "eval_request", "round": number, "run": run, "turn": turn,
                      "turn_sha256": _sha(turn_text.encode("utf-8")), "reading_file": reading_file,
                      "written_at": _now()})
    request_sha = _sha(request)
    _write(request_path, request)
    _log(rec, "request_written", path=request_path, sha256=request_sha)

    seen: set = set()
    while True:
        got = _read_json(reading_file)
        if got is not None:
            raw, body = got
            tag = body.get("bridge")
            if isinstance(tag, dict) and _int(tag.get("round")) and tag.get("round") == number \
                    and _int(tag.get("run")) and tag.get("run") == run \
                    and tag.get("request_sha256") == request_sha:
                break
            _ignore_once(rec, seen, raw, "reading_ignored", "its bridge object names another request")
        time.sleep(poll)
    _log(rec, "reading_accepted", path=reading_file, sha256=_sha(raw))
    _write_cost(rec, cost_path, tag, reading_file, _sha(raw))
    _log(rec, "evaluator_done", exit=0)
    sys.stdout.buffer.write(raw)
    sys.stdout.flush()
    return 0


def _poll(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        value = float("nan")
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError("--poll must be a positive number of seconds")
    return value


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="seat_bridge.py", description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("maker", "evaluator"))
    parser.add_argument("--poll", type=_poll, default=1.0, help="seconds between looks (default 1.0)")
    args = parser.parse_args(argv)
    try:
        return maker(args.poll) if args.command == "maker" else evaluator(args.poll)
    except Refused as exc:
        sys.stderr.write("seat_bridge %s: refused: %s\n" % (args.command, exc))
        cost = os.environ.get("PLUMBLINE_COST", "")
        if cost.strip() and os.path.isdir(os.path.join(os.path.dirname(os.path.abspath(cost)), "bridge")):
            try:
                _log(os.path.dirname(os.path.abspath(cost)), "refused", command=args.command, reason=str(exc))
            except OSError:
                pass
        return 2
    except OSError as exc:  # e.g. an unwritable R: one line, no traceback
        sys.stderr.write("seat_bridge %s: cannot write under the record dir: %s\n" % (args.command, exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Emit a job packet — the machine-readable terms of a job — or emit nothing.

WHY THIS EXISTS. A job closed `needs_owner` with its terms in `packet.md`: prose, so the gate could not read a
single field of it, and every downstream check that depends on those terms was reduced to reading English. The
kit's first cross-machine reading found exactly this on four consecutive jobs. The shape existed the whole time
(a ratified packet validated `OK (schema-verified)`); what was missing was anything that PRINTS it.

THE RULE IT FOLLOWS. It does not carry its own copy of the law. It reads the corpus schema's `required` list
at runtime and checks presence against THAT, then mirrors the cross-rules a schema cannot express (scored vs
readings prohibitions, entry B's reads, seat separation, the terminal/outcome map) — each naming the gate's own
reason. Then it runs the corpus gate on its own output. A packet the gate cannot read is not a job's terms.

IT ADDS ONLY KEYS THE LAW DECLARES. The machine-supplied facts (the doctrine pin, the constitution reference)
are stamped only where the corpus schema already declares the property — never as an extra key, because an
unknown key is how a packet comes to fail `additionalProperties: false` and how an instance invents law.

    emit_packet.py --brief brief.json --out-dir <job dir> [--corpus PATH] [--print-only]

brief.json — the Buyer's and Architect's terms, as fields rather than paragraphs. Every key is the corpus's
own name; run with --print-only to see what the schema requires of you.
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from pathlib import Path

TERMINALS = {"accepted", "needs_owner", "rejected"}
OUTCOMES = {"accepted", "census", "needs_owner", "rejected", "no_observation", "no_artifact"}
OUTCOME_MAP = {"accepted": "accepted", "census": "accepted", "needs_owner": "needs_owner",
               "rejected": "rejected", "no_observation": "needs_owner", "no_artifact": "needs_owner"}
BOUND_KEYS = ("T_accept", "T_dim", "T_reject", "cap", "budget")
# The gate itself checks Owner-is-not-Evaluator. Maker-never-grades-its-own-work is §4's rule and the gate does
# not read it, so it is checked here and NAMED as this instance's addition rather than the corpus's.
INSTANCE_ADDED = {"maker_is_not_evaluator": "§4.1/rule 10 — the Maker never grades its own work"}


def blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or v in ({}, [])


def seats(packet: dict) -> tuple[str, str]:
    def name(v):
        if isinstance(v, dict):
            for k in ("name", "who", "seat", "holder"):
                if isinstance(v.get(k), str) and v[k].strip():
                    return v[k].strip()
            return ""
        return v.strip() if isinstance(v, str) else ""
    return name(packet.get("maker")), name(packet.get("evaluator"))


KINDS = ("person", "model", "script")


def kind_note(p: dict) -> str:
    """Contracts §4 (v1.26.0): who holds the Evaluator seat is recorded with the job, as `evaluator.kind`.
    Optional in the schema today, so its absence is a NOTE, never a refusal. The emitter does not guess it: only
    the brief knows whether a person, a model or a script holds the seat."""
    ev = p.get("evaluator")
    if isinstance(ev, dict) and ev.get("kind") in KINDS:
        return ""
    return ("NOTE evaluator.kind not recorded — Contracts §4 records who holds the Evaluator seat; give the "
            "brief's evaluator as {\"name\": ..., \"kind\": \"person\" | \"model\" | \"script\"}")


def refusals(p: dict, required: list[str]) -> list[str]:
    out = []
    for k in required:                                    # the law's own list, read from the corpus schema
        if k not in p:
            out.append(f"missing required: {k}")
    if not blank(p.get("entry")) and p["entry"] not in ("A", "B"):
        out.append(f"entry must be A|B, got {p['entry']!r}")
    if not blank(p.get("instrument_profile")) and p["instrument_profile"] not in ("full", "mvi"):
        out.append(f"instrument_profile must be full|mvi, got {p['instrument_profile']!r}")
    mode = p.get("mode")
    if not blank(mode) and mode not in ("scored", "readings"):
        out.append(f"mode must be scored|readings, got {mode!r}")
    if p.get("terminal_state") and p["terminal_state"] not in TERMINALS:
        out.append(f"illegal terminal_state: {p['terminal_state']!r}")
    if "outcome" in p and p["outcome"] not in OUTCOMES:
        out.append(f"outcome must be one of the six: {p['outcome']!r}")
    elif "outcome" in p and p.get("terminal_state") and OUTCOME_MAP[p["outcome"]] != p["terminal_state"]:
        out.append(f"outcome {p['outcome']} requires terminal_state {OUTCOME_MAP[p['outcome']]}, "
                   f"got {p['terminal_state']!r}")
    if p.get("ratified") is False:
        if p.get("terminal_state") == "accepted":
            out.append("ratified:false cannot have terminal_state accepted — an unratified job can never be accepted")
        for k in ("bounds", "specialist", "standard_ref"):
            if k in p:
                out.append(f"ratified:false must not have top-level {k}")
    else:
        for k in ("human_seat", "standard_ref"):
            if blank(p.get(k)):
                out.append(f"missing required: {k} — a ratified job names who holds the human seat and the "
                           f"standard the work is measured against")
    if p.get("entry") == "B" and blank(p.get("reads_before_freeze")):
        out.append("entry B requires non-empty reads_before_freeze (C32) — which reads could reveal a defect, "
                   "and the statement that they came after the rubric was frozen")
    if mode == "readings":
        for k in ("bounds", "specialist"):
            if k in p:
                out.append(f"readings mode must not supply {k} — no thresholds means no floor to be below, "
                           f"so a readings job may not reject")
        if p.get("outcome") == "rejected" or p.get("terminal_state") == "rejected":
            out.append("readings mode may not produce rejected")
    if mode == "scored":
        if blank(p.get("specialist")):
            out.append("scored mode missing: specialist — mode:scored requires a Specialist named at the outset")
        b = p.get("bounds")
        if blank(b):
            out.append("scored mode missing: bounds object")
        elif isinstance(b, dict):
            for k in BOUND_KEYS:
                if k not in b:
                    out.append(f"scored bounds missing: {k}")
        gt = p.get("ground_truth")
        if blank(gt):
            out.append("scored mode missing: ground_truth")
        elif isinstance(gt, list):
            for i, row in enumerate(gt):
                if not isinstance(row, dict):
                    out.append(f"ground_truth[{i}] must be an object")
                    continue
                for k in ("ref", "version", "hardness"):
                    if blank(row.get(k)):
                        out.append(f"ground_truth[{i}] missing: {k}")
                if row.get("hardness") not in (None, "") and row["hardness"] not in ("INVARIANT", "DOCUMENT", "PRIOR"):
                    out.append(f"ground_truth[{i}] hardness must be INVARIANT|DOCUMENT|PRIOR")
        m = p.get("mandate_ref")
        if blank(m):
            out.append("scored mode missing: mandate_ref")
        elif isinstance(m, dict):
            for k in ("doc", "version"):
                if blank(m.get(k)):
                    out.append(f"mandate_ref missing: {k}")
        if blank(p.get("escalation")):
            out.append("scored mode missing: escalation — who is raised to, and on what")
        # contracts/EDI-MANDATE.md §7 B.1.2: "material misalignment is found by iteration ≤ k, or within x% of budget", declared before the run.
        # Declared AT OPEN, because a bound declared after the fact is not a bound — and O2's rate has no
        # numerator without it. The corpus declares neither field, so this is Plumbline's own requirement.
        for bound in ("k", "x"):
            if p.get(bound) is None:
                out.append(f"scored mode missing: {bound} — B.1.2 declares k (the iteration bound) and x (the "
                           f"budget tolerance) PER JOB, and a bound written after the run is not a bound")
    mk, ev = seats(p)
    if ev.strip().lower() == "owner":
        out.append("Owner must not hold the Evaluator seat (§4)")
    elif mk and ev and mk.lower() == ev.lower():
        out.append(f"maker and evaluator are the same party ({ev!r}) — {INSTANCE_ADDED['maker_is_not_evaluator']}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Emit a job packet the gate can read, or emit nothing.")
    ap.add_argument("--brief", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--corpus")
    ap.add_argument("--print-only", action="store_true")
    a = ap.parse_args()

    corpus = a.corpus or os.environ.get("EDI_CORPUS") or ""
    schema_path = Path(corpus) / "schemas" / "job-packet.schema.json" if corpus else None
    if not corpus or not schema_path or not schema_path.is_file():
        print(f"REFUSED: no corpus resolved (--corpus or $EDI_CORPUS). The emitter will not carry its own copy "
              f"of the law: it reads the corpus schema's required list, then runs the corpus gate.")
        return 2
    schema = json.loads(schema_path.read_text())
    required = list(schema.get("required", []))

    brief = json.loads(Path(a.brief).read_text())
    out = Path(a.out_dir).expanduser()
    if not out.is_dir():
        print(f"REFUSED: --out-dir is not a job directory: {out}"); return 2

    packet = dict(brief)
    # machine-supplied facts, stamped ONLY where the law already declares the property
    declared = set((schema.get("properties") or {}).keys())
    if "edi_pin" in declared and blank(packet.get("edi_pin")):
        try:
            rev = subprocess.run(["git", "-C", str(corpus), "rev-parse", "HEAD"], capture_output=True,
                                 text=True, check=True).stdout.strip()
            packet["edi_pin"] = rev
        except Exception:
            pass

    stops = refusals(packet, required)
    if stops:
        print(f"REFUSED — {len(stops)} reason(s) this brief cannot become a packet:")
        for s in stops:
            print(f"  - {s}")
        print(f"\nthe law's required keys are: {', '.join(required)}")
        print("nothing written. The terms of a job are the one thing a tool must not guess.")
        return 1

    path = out / "packet.json"
    note = kind_note(packet)
    if note:
        print(note)
    if a.print_only:
        print(f"would write {path} ({len(packet)} keys, all declared by the corpus schema)")
        print(json.dumps(packet, indent=2)[:800]); return 0

    # THE GATE RUNS BEFORE THE FILE LANDS. A packet the gate rejected is not a job's terms, and leaving one on
    # disk makes the next reader think the job declared something it did not. Measured 2026-10-05: the first cut
    # wrote packet.json and then reported the gate's error, which is the wrong order for a record of terms.
    gate = Path(corpus) / "tools" / "validate_job_packet.py"
    staged = out / ".packet.json.staged"
    staged.write_text(json.dumps(packet, indent=2) + "\n")
    r = subprocess.run([sys.executable, str(gate), str(staged)], capture_output=True, text=True)
    verdict = (r.stdout + r.stderr).strip()
    if r.returncode != 0:
        staged.unlink(missing_ok=True)
        print("the corpus gate REJECTED this packet — nothing left behind:")
        print("  " + verdict.replace("\n", "\n  "))
        print("  fix the brief, not the gate.")
        return r.returncode
    staged.replace(path)
    print(f"wrote {path.name}")
    print("  " + verdict.replace("\n", "\n  "))
    return 0


if __name__ == "__main__":
    sys.exit(main())

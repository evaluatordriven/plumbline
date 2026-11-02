#!/usr/bin/env python3
"""Derive Plumbline's schemas and compliance checklist from the pinned E-DI corpus.

WHY THIS EXISTS
    Plumbline shipped a second job-packet schema that disagreed with the corpus's own
    (measured: the corpus's fixtures give 18 errors against it). Two live schemas for one
    law means neither is authority, and a hand-copied schema drifts silently. So every
    Plumbline schema is now DERIVED here from the corpus at a pinned commit:

        corpus (machine authority, Contracts + schemas/) + instance-extensions.json
            -> schemas/job-packet.schema.json          (derived, never hand-edited)
            -> schemas/evaluator-record.schema.json    (derived, verbatim corpus shape)
            -> schemas/audit-record.schema.json        (derived, corpus shape + audit extensions)
            -> schemas/compliance-checklist.json       (derived from Contracts §9, `why` re-attached by id)

    Doctrine this obeys: Contracts §12 (version bump regenerates derived artifacts),
    §8/C18 (the instance layer is labelled and weakens nothing), and the corpus's own
    lesson that an artifact carrying authored content is rebuilt from source with its
    annotations re-attached BY ID — not regenerated wholesale (loses annotations) and not
    patched indefinitely (drifts).

CORPUS RESOLUTION (tools/edi_corpus.py, the one shared resolver)
    --corpus, else $EDI_CORPUS, else plugins.edi-loop.corpus in $HERMES_HOME/config.yaml or
    ~/.hermes/config.yaml. A value that is set but is not a corpus is an error naming the path; it never
    falls through. No homedir guessing — a wrong guess produces a silent stale build.

VENDORED COPY (schemas/vendor/e-di@<pin8>/, VENDOR.json)
    The corpus's two schemas and its fixture battery are vendored byte-for-byte, so the alignment checks
    run with no corpus at all. `--check` ALWAYS verifies every vendored file against its VENDOR.json
    sha256 and the two vendored schemas against tools/pin.json `files`. With no corpus it then prints
    `SKIP[corpus] corpus.build-check` and exits 0 (FAIL and exit 1 under PLUMBLINE_REQUIRE_CORPUS=1).
    With a corpus it also verifies the corpus is a git checkout of its own (else COMMIT NOT VERIFIABLE),
    at the pinned commit with the pinned hashes (else DRIFT), and rebuilds every derived file in memory
    and compares it with the committed bytes.

PIN DISCIPLINE
    tools/pin.json records the corpus commit and every source file's sha256. The build FAILS
    LOUD when the corpus has moved, and only --repin re-pins. A derived artifact nobody can
    attribute to a source revision is not evidence.

CUSTODY (custody/v1 records, added 2026-10-27)
    The same discipline, for the second authority Plumbline now writes against:

        custody (evaluatordriven/custody @ pinned commit: schema/custody-v1.schema.json)
          + instance-extensions.json `custody_record`
            -> schemas/custody/custody-v1.schema.json   (VENDORED byte-for-byte; never edited)
            -> schemas/custody-record.schema.json       (derived, never hand-edited)

    The custody pin lives in tools/pin.json under `custody` (the corpus pin is untouched; a
    corpus build carries the custody section over unchanged). The custody checkout comes from
    --custody-dir or $CUSTODY_DIR; nothing here needs the E-DI corpus or ~/.hermes.

        build_schemas.py --custody --check [--require-upstream]   drift check, writes nothing
        build_schemas.py --custody [--repin]                      re-derive (re-pin deliberately)

    --check FAILS when: the checkout is not at the pinned commit or any pinned custody file's
    sha256 differs (custody moved); the vendored copy differs from the pin; or a derived schema
    is not byte-identical to what the derivation produces now (hand edit).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SHIP = REPO / "schemas"
INSTANCE = SHIP / "instance-extensions.json"
PIN = REPO / "tools" / "pin.json"

CORPUS_FILES = [
    "EDI-PLAYBOOK.md",
    "EDI-QUICKSTART.md",
    "EDI-OPERATING-INSTRUMENT.md",
    "EDI-MACHINE-CONTRACTS.md",
    "EDI-MANDATE.md",
    "EDI-EXAMPLE.md",
    "EDI-FOR-MACHINES.md",
    "schemas/job-packet.schema.json",
    "schemas/evaluator-record.schema.json",
    "EDI-RULE-INDEX.json",
]


# What tools/pin.json records as the corpus. A label, never a local path: the checkout lives wherever
# the runner keeps it and is resolved at run time through --corpus or $EDI_CORPUS (see resolve_corpus).
CORPUS_LABEL = "github.com/evaluatordriven/doctrine"
# Where the load set sits inside that repository. The resolved corpus must be exactly <git top level>/<this>.
CORPUS_PATH = "contracts"
# Files ABOVE the load set, read from the git top level. Pinned by sha256 so --check reports their drift; they are
# not derived from, so a change to them is drift to re-read, never a schema change.
DOCTRINE_FILES = ["DOCTRINE.md", "AUTHORITY.json"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


sys.path.insert(0, str(Path(__file__).resolve().parent))
import edi_corpus  # noqa: E402  (tools/edi_corpus.py: the shared D-E resolver)

# What a corpus must hold for this tool: the pinned sources plus the corpus's own validator.
CORPUS_NEED = tuple(CORPUS_FILES) + ("tools/validate_job_packet.py",)
CHECK_ID = "corpus.build-check"
VENDORED_SCHEMAS = ("schemas/job-packet.schema.json", "schemas/evaluator-record.schema.json")


def resolve_corpus(explicit: str = "") -> "edi_corpus.Corpus | None":
    """The corpus, or None. A set value that is not a corpus exits 2 naming it (tools/edi_corpus.py)."""
    corpus, _ = edi_corpus.resolve_or_exit(explicit or None, CORPUS_NEED)
    return corpus


def vendor_dir(pin: dict) -> Path:
    return SHIP / "vendor" / f"e-di@{pin['commit'][:8]}"


def check_vendored(pin: dict) -> list[str]:
    """Every vendored file against VENDOR.json, and the two vendored schemas against tools/pin.json."""
    vdir = vendor_dir(pin)
    vj = vdir / "VENDOR.json"
    rel = lambda q: q.relative_to(REPO).as_posix()  # noqa: E731
    if not vj.is_file():
        return [f"{rel(vj)} is missing: the vendored copy cannot be verified"]
    try:
        vendor = json.loads(vj.read_text(encoding="utf-8"))
        files = vendor["files"]
    except Exception as e:  # noqa: BLE001
        return [f"{rel(vj)} does not parse or has no `files`: {e}"]
    problems = []
    if vendor.get("commit") != pin.get("commit"):
        problems.append(f"{rel(vj)} commit {str(vendor.get('commit'))[:12]} is not the tools/pin.json commit "
                        f"{pin.get('commit', '')[:12]}")
    for name, entry in files.items():
        f = vdir / name
        if not f.is_file():
            problems.append(f"{rel(f)} is missing (listed in VENDOR.json)")
        elif sha256(f) != entry.get("sha256"):
            problems.append(f"{rel(f)} sha256 {sha256(f)[:16]} differs from VENDOR.json {str(entry.get('sha256'))[:16]}")
    on_disk = {q.relative_to(vdir).as_posix() for q in vdir.rglob("*") if q.is_file()} - {"VENDOR.json"}
    for extra in sorted(on_disk - set(files)):
        problems.append(f"{rel(vdir / extra)} is not listed in VENDOR.json")
    for orig in VENDORED_SCHEMAS:
        f = vdir / Path(orig).name
        want = pin.get("files", {}).get(orig)
        if f.is_file() and sha256(f) != want:
            problems.append(f"{rel(f)} sha256 {sha256(f)[:16]} differs from tools/pin.json files[{orig}] {str(want)[:16]}")
        if files.get(Path(orig).name, {}).get("original_path") not in (None, orig):
            problems.append(f"{rel(vj)} gives {Path(orig).name} an original_path other than {orig}")
    return problems


def git_toplevel(corpus: Path) -> Path | None:
    try:
        out = subprocess.run(["git", "-C", str(corpus), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, check=True).stdout.strip()
        return Path(out).resolve() if out else None
    except Exception:  # noqa: BLE001
        return None


def doctrine_hashes(corpus: Path) -> dict:
    """sha256 of DOCTRINE_FILES at the corpus's git top level; a missing file records None (drift if pinned)."""
    top = git_toplevel(corpus) or corpus.parent
    return {f: (sha256(top / f) if (top / f).is_file() else None) for f in DOCTRINE_FILES}


def corpus_commit(corpus: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(corpus), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return "unknown-not-a-git-checkout"


def coverage_state(corpus: Path) -> dict:
    idx = json.loads((corpus / "EDI-RULE-INDEX.json").read_text(encoding="utf-8"))
    return {
        "contracts_version": idx.get("contracts_version"),
        "counts": idx.get("counts"),
        "generated_from": idx.get("generated_from"),
    }


# --------------------------------------------------------------------------- schemas

def merge_packet(base: dict, inst: dict, pin: dict) -> dict:
    out = json.loads(json.dumps(base))  # deep copy, corpus shape kept intact
    out["$id"] = "plumbline/schemas/job-packet.schema.json"
    out["title"] = "Plumbline job packet (derived: E-DI corpus §3 + §6, plus the Plumbline instance layer)"
    out["description"] = (
        "DERIVED — do not hand-edit; regenerate with tools/build_schemas.py. "
        f"Corpus machine authority: {pin['corpus']}@{pin['commit'][:12]} "
        f"(Contracts v{pin['coverage']['contracts_version']}). "
        "Field names are the corpus's; the instance layer is confined to the properties its own "
        "descriptions label INSTANCE-SPECIFIC (Contracts §8 / C18). "
        "While ratified=false the must-ask values may live ONLY in the top-level `proposed` block and "
        "the loop's only possible terminal state is needs_owner — enforced structurally here, and in the "
        "corpus schema this file composes."
    )
    props = dict(out.get("properties", {}))
    props.update(inst["packet_properties"])
    out["properties"] = props
    out["required"] = list(dict.fromkeys(list(out.get("required", [])) + list(inst["packet_required"])))
    defs = dict(out.get("$defs", {}))
    defs.update(inst["packet_defs"])
    out["$defs"] = defs
    # instance if/then rules are APPENDED: a corpus rule may never be replaced by an instance rule.
    out["allOf"] = list(out.get("allOf", [])) + list(inst["packet_all_of"])
    return out


def derive_record(base: dict, pin: dict) -> dict:
    out = json.loads(json.dumps(base))
    out["$id"] = "plumbline/schemas/evaluator-record.schema.json"
    out["title"] = "Plumbline §5 evaluator record (derived verbatim from the corpus)"
    out["description"] = (
        "DERIVED — do not hand-edit; regenerate with tools/build_schemas.py. "
        f"Corpus machine authority: {pin['corpus']}@{pin['commit'][:12]} (Contracts v{pin['coverage']['contracts_version']}). "
        "Copied shape-for-shape: field names, requiredness and additionalProperties are the corpus's. "
        "Plumbline additions travel in instance_extensions[] (name + label:'instance-specific' + value), never "
        "as new top-level fields, so every record still validates against the corpus §5 shape."
    )
    return out


def derive_audit(record: dict, inst: dict, pin: dict) -> dict:
    out = json.loads(json.dumps(record))
    out["$id"] = "plumbline/schemas/audit-record.schema.json"
    out["title"] = "Plumbline conformance audit record (derived: corpus §5 + audit extensions)"
    out["description"] = (
        "DERIVED — do not hand-edit; regenerate with tools/build_schemas.py. "
        f"Corpus machine authority: {pin['corpus']}@{pin['commit'][:12]}. "
        "An audit IS a §5 evaluator run whose subject is an instance rather than an artifact, so it must "
        "validate against the corpus §5 schema unchanged — the audit-specific fields ride inside "
        "instance_extensions, and this schema requires the three that make a finding checkable: "
        + ", ".join(inst["record_extension_conventions"]["audit_required_extensions"])
        + ". If Plumbline's own output were prose, Plumbline would fail the doctrine it enforces."
    )
    ext = out.setdefault("properties", {}).setdefault("instance_extensions", {})
    required_ext = inst["record_extension_conventions"]["audit_required_extensions"]
    out.setdefault("allOf", []).extend(
        [
            {
                "properties": {
                    "instance_extensions": {
                        "contains": {
                            "type": "object",
                            "required": ["name", "label"],
                            "properties": {"name": {"const": name}},
                        },
                        "minContains": 1,
                    }
                }
            }
            for name in required_ext
        ]
    )
    return out


# ------------------------------------------------------------------------ checklist

CLAUSE_RE = re.compile(r"^\|\s*(?:\*{0,2})(?:~~)?\s*(C\d+)\s*(?:~~)?(?:\*{0,2})\s*\|([^|]*)\|([^|]*)\|\s*$")
RETIRED_RE = re.compile(r"~~\s*(C\d+)\s*~~|RETIRED")


def parse_clauses(contracts_md: str) -> list[dict]:
    clauses, retired = [], set()
    for line in contracts_md.splitlines():
        m = CLAUSE_RE.match(line)
        if not m:
            continue
        cid, text, section = m.group(1), m.group(2).strip(), m.group(3).strip()
        if RETIRED_RE.search(line):
            retired.add(cid)
            continue
        clauses.append(
            {
                "id": cid,
                "clause": re.sub(r"\*\*", "", text).strip(),
                "section": re.sub(r"\*\*", "", section).strip(),
            }
        )
    return clauses


def rebuild_checklist(corpus: Path, pin: dict, previous: dict | None) -> dict:
    contracts = (corpus / "EDI-MACHINE-CONTRACTS.md").read_text(encoding="utf-8")
    clauses = parse_clauses(contracts)
    if not clauses:
        raise SystemExit("checklist rebuild: parsed 0 §9 clauses — refusing to write an empty surface")

    why_by_id = {}
    if previous:
        for c in previous.get("clauses", []):
            if c.get("why"):
                why_by_id[c["id"]] = c["why"]
    for c in clauses:
        if c["id"] in why_by_id:
            c["why"] = why_by_id[c["id"]]          # annotations re-attached BY ID
    reattached = sum(1 for c in clauses if "why" in c)

    ids = [c["id"] for c in clauses]
    retired = sorted(
        m.group(1) for line in contracts.splitlines()
        if (m := re.search(r"~~\s*(C\d+)\s*~~", line))
    )
    # §9 is contiguous EXCEPT for retired ids, which stay reserved and are never renumbered
    # (Contracts §12: a line's identifier is cited in filed audits and never changes meaning).
    max_n = max(int(i[1:]) for i in ids)
    expected = [f"C{i}" for i in range(1, max_n + 1)]
    missing = [i for i in expected if i not in set(ids)]
    unexplained = [i for i in missing if i not in retired]
    if ids != sorted(ids, key=lambda s: int(s[1:])):
        raise SystemExit(f"checklist rebuild: §9 ids are out of order — {ids[:6]}...")
    if unexplained:
        raise SystemExit(
            f"checklist rebuild: §9 has unexplained gaps {unexplained} (retired/reserved: {retired}) — "
            "a gap is legal only for a reserved id; otherwise the parse is wrong."
        )
    if len(ids) != len(set(ids)):
        raise SystemExit("checklist rebuild: duplicate §9 ids — the parse is wrong.")
    return {
        "$schema": "plumbline/schemas/compliance-checklist.json",
        "title": f"E-DI Contracts §9 compliance checklist — machine-readable (v{pin['coverage']['contracts_version']})",
        "description": (
            "DERIVED from Contracts §9 by tools/build_schemas.py, with the authored `why` annotations "
            "re-attached by clause id (they are authored, not generated — a wholesale regeneration loses them). "
            "Ids are stable and never renumbered (Contracts §12); retired ids stay reserved."
        ),
        "contracts_version": pin["coverage"]["contracts_version"],
        "contracts_source": f"{pin['corpus']}@{pin['commit'][:12]} (EDI-MACHINE-CONTRACTS.md)",
        "contracts_sha256": pin["files"]["EDI-MACHINE-CONTRACTS.md"],
        "rule_index": {
            "in_scope": pin["coverage"]["counts"]["in_scope"],
            "line": pin["coverage"]["counts"]["line"],
            "schema": pin["coverage"]["counts"]["schema"],
            "none": pin["coverage"]["counts"]["none"],
            "uncovered": pin["coverage"]["counts"]["uncovered"],
            "note": "Published by the corpus in EDI-RULE-INDEX.json. Every NORMATIVE rule has exactly one disposition; an uncovered rule is a corpus defect, not an implementation one.",
        },
        "outcomes_vocabulary": {
            "note": "The corpus's readings vocabulary (Instrument, 'Readings — and when scoring is allowed'), aligned here so the audit speaks the doctrine's words. The pre-2026-09-29 names (pass / fail / not_assessed) are aliases only.",
            "conforms": "The clause holds, with the observation cited.",
            "does_not_conform": "The clause does not hold, or holds only partially. The observation must name which part holds and which does not.",
            "not_assessed": "The auditor did not inspect the code path this clause covers. NOT the same as does_not_conform: this is 'could not be judged', which per §5 forces needs_owner, never rejected.",
        },
        "scoring": {
            "method": "clause score: 10 = conforms, 5 = does_not_conform; not_assessed clauses are omitted from dimensions and listed in unjudged_dimensions",
            "rationale": "§3 requires a mean threshold AND a per-dimension floor. For conformance both are 10: every clause must hold. A non-conformance scores above the reject floor deliberately — a divergence is remediable and opens a new job, it is not a discarded artifact.",
        },
        "provenance": {
            "clauses_parsed": len(clauses),
            "annotations_reattached": reattached,
            "retired_ids_reserved": retired,
        },
        "clauses": clauses,
    }


# ----------------------------------------------------------------------------- custody/v1

CUSTODY_SCHEMA_REL = "schema/custody-v1.schema.json"
CUSTODY_VENDORED = SHIP / "custody" / "custody-v1.schema.json"
CUSTODY_DERIVED = SHIP / "custody-record.schema.json"
CUSTODY_DERIVED_ID = "urn:plumbline:schemas:custody-record"


def custody_commit(d: Path) -> str:
    """HEAD of a custody checkout, or "" when it is not a git checkout (then only file digests can speak)."""
    if not (d / ".git").exists():
        return ""
    try:
        return subprocess.run(["git", "-C", str(d), "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True, env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1"}).stdout.strip()
    except Exception:
        return ""


def derive_custody(pinned_bytes: bytes, inst: dict, cpin: dict) -> dict:
    """custody/v1 as Plumbline emits it: allOf(the pinned schema, embedded verbatim, + the instance rules).

    The section-4 key lists are READ FROM the pinned schema (its own `properties`), never typed here, so a
    custody release that adds a field changes this output — which the --check then reports as drift."""
    base = json.loads(pinned_bytes.decode("utf-8"))
    rules = inst["custody_record"]
    xk = rules["x_key"]
    pred_keys = sorted(base["$defs"]["predicate"]["properties"])
    root_keys = sorted(base["properties"])
    x_any = {"pattern": "^x-"}
    overlay = {
        "propertyNames": {"anyOf": [{"enum": root_keys}, x_any]},
        "properties": {"predicate": {
            "required": [xk],
            "propertyNames": {"anyOf": [{"enum": pred_keys}, x_any]},
            "properties": {
                xk: {"type": "object", "required": list(rules["predicate_x_required"]),
                     "properties": {"verdict": {"enum": list(rules["verdicts"])},
                                    "terminal_state": {"enum": list(rules["terminal_states"])},
                                    "job_id": {"type": "string", "minLength": 1}}},
                "violations": {"items": {"required": [xk],
                                         "properties": {xk: {"type": "object", "required": ["locator"],
                                                             "properties": {"locator": {"enum": list(rules["violation_locators"])}}}}}},
            },
        }},
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": CUSTODY_DERIVED_ID,
        "title": "Plumbline custody/v1 record (DERIVED — do not hand-edit; run tools/build_schemas.py --custody)",
        "description": (f"Derived by tools/build_schemas.py from custody {cpin['source']}@{cpin['commit'][:12]} "
                        f"({CUSTODY_SCHEMA_REL} sha256 {cpin['files'][CUSTODY_SCHEMA_REL]}) plus "
                        f"schemas/instance-extensions.json `custody_record` (instance-specific). Every record valid "
                        f"here is valid against the pinned custody schema: this layer only adds constraints."),
        "x-derivedFrom": {"custody": {"source": cpin["source"], "commit": cpin["commit"],
                                      "schema_sha256": cpin["files"][CUSTODY_SCHEMA_REL]},
                          "instance_layer": "schemas/instance-extensions.json#custody_record"},
        "allOf": [{"$ref": base["$id"]}, overlay],
        "$defs": {"custody-v1": base},
    }


def custody_main(args) -> int:
    pin = json.loads(PIN.read_text(encoding="utf-8")) if PIN.is_file() else {}
    cpin = pin.get("custody")
    cdir_s = args.custody_dir or os.environ.get("CUSTODY_DIR", "")
    cdir = Path(cdir_s).expanduser() if cdir_s else None
    inst = json.loads(INSTANCE.read_text(encoding="utf-8"))
    problems, notes = [], []

    if not cpin:
        print("NO CUSTODY PIN in tools/pin.json — run --custody --repin with a checkout to establish one")
        return 1

    # 1. the upstream checkout, when one is given
    if cdir is not None:
        if not (cdir / CUSTODY_SCHEMA_REL).is_file():
            problems.append(f"custody checkout {cdir} has no {CUSTODY_SCHEMA_REL}")
        else:
            head = custody_commit(cdir)
            if head and head != cpin["commit"]:
                problems.append(f"custody commit {cpin['commit'][:12]} -> {head[:12]}")
            if not head:
                notes.append(f"{cdir} is not a git checkout: commit not compared, file digests only")
            for f, h in cpin["files"].items():
                live = sha256(cdir / f) if (cdir / f).is_file() else "(absent)"
                if live != h:
                    problems.append(f"custody {f} changed ({h[:12]} pinned, {live[:12]} found)")
    elif args.require_upstream:
        print("NOT VERIFIED: no custody checkout (--custody-dir or $CUSTODY_DIR) and --require-upstream was given")
        return 2
    else:
        notes.append("UPSTREAM NOT COMPARED: no --custody-dir / $CUSTODY_DIR — only the vendored copy and the "
                     "derived schema were checked (this is a partial check, not a pass of the upstream pin)")

    if args.check:
        # 2. the vendored copy is the pinned schema, byte for byte
        if not CUSTODY_VENDORED.is_file():
            problems.append(f"vendored custody schema missing: {CUSTODY_VENDORED.relative_to(REPO)}")
        elif sha256(CUSTODY_VENDORED) != cpin["files"][CUSTODY_SCHEMA_REL]:
            problems.append(f"vendored {CUSTODY_VENDORED.relative_to(REPO)} is not the pinned schema (edited or stale)")
        # 3. every derived schema is exactly what the derivation produces from the pinned bytes
        if CUSTODY_VENDORED.is_file() and not problems:
            want = json.dumps(derive_custody(CUSTODY_VENDORED.read_bytes(), inst, cpin), indent=2) + "\n"
            for rel in cpin.get("derived", []):
                f = REPO / rel
                if not f.is_file():
                    problems.append(f"derived custody schema missing: {rel}")
                elif f.read_text(encoding="utf-8") != want:
                    problems.append(f"derived {rel} differs from its derivation (hand-edited, or instance layer "
                                    f"changed without a rebuild)")
        for n in notes:
            print(f"note: {n}")
        if problems:
            print("CUSTODY DRIFT:")
            for p in problems:
                print(f"  - {p}")
            print("Re-read the changed custody SPEC/schema, then rebuild with --custody --repin.")
            return 1
        print(f"CUSTODY PIN OK  {cpin['source']}@{cpin['commit'][:12]}  schema {cpin['files'][CUSTODY_SCHEMA_REL][:12]}"
              f"  derived: {', '.join(cpin.get('derived', []))}")
        return 0

    # build (re-derive); re-pin only when asked
    if cdir is None:
        print("REFUSING TO BUILD: a custody build needs the checkout (--custody-dir or $CUSTODY_DIR)")
        return 2
    if problems and not args.repin:
        print("REFUSING TO BUILD: custody moved since the last pin:")
        for p in problems:
            print(f"  - {p}")
        print("Re-read the changed custody SPEC/schema, then re-run with --custody --repin.")
        return 1
    if args.repin:
        head = custody_commit(cdir)
        if not head:
            print("REFUSING TO RE-PIN: the custody checkout is not a git checkout, so no commit can be pinned")
            return 1
        cpin = {**cpin, "commit": head, "files": {f: sha256(cdir / f) for f in cpin["files"]}}
    CUSTODY_VENDORED.parent.mkdir(parents=True, exist_ok=True)
    CUSTODY_VENDORED.write_bytes((cdir / CUSTODY_SCHEMA_REL).read_bytes())
    derived = derive_custody(CUSTODY_VENDORED.read_bytes(), inst, cpin)
    CUSTODY_DERIVED.write_text(json.dumps(derived, indent=2) + "\n", encoding="utf-8")
    pin["custody"] = {**cpin, "derived": [str(CUSTODY_DERIVED.relative_to(REPO))]}
    PIN.write_text(json.dumps(pin, indent=2) + "\n", encoding="utf-8")
    print(f"custody     pinned {cpin['source']}@{cpin['commit'][:12]}; vendored {CUSTODY_VENDORED.relative_to(REPO)}; "
          f"derived {CUSTODY_DERIVED.relative_to(REPO)}")
    return 0


# ----------------------------------------------------------------------------- derive + check

def derive_all(corpus: Path, commit: str, hashes: dict, coverage: dict, old_pin: dict | None):
    """Everything build mode writes, as {path: text}, computed in memory (build writes it; --check compares)."""
    inst = json.loads(INSTANCE.read_text(encoding="utf-8"))
    pin = {
        "corpus": CORPUS_LABEL,
        "path": CORPUS_PATH,
        "commit": commit,
        "files": hashes,
        "doctrine_files": doctrine_hashes(corpus),
        "coverage": coverage,
        "note": "Generated by tools/build_schemas.py. Every derived schema names this pin, so a reader can attribute a rule to the revision it came from. `corpus` names the source repository (public), not a local path, and `path` the load set inside it: point --corpus or $EDI_CORPUS at <a checkout of it>/contracts. `doctrine_files` are pinned for drift only; nothing is derived from them.",
    }
    if old_pin and "custody" in old_pin:          # a corpus build never drops the custody pin (--custody owns it)
        pin["custody"] = old_pin["custody"]

    base_packet = json.loads((corpus / "schemas" / "job-packet.schema.json").read_text(encoding="utf-8"))
    base_record = json.loads((corpus / "schemas" / "evaluator-record.schema.json").read_text(encoding="utf-8"))

    derived_packet = merge_packet(base_packet, inst, pin)
    derived_record = derive_record(base_record, pin)
    derived_audit = derive_audit(base_record, inst, pin)

    previous_checklist = None
    cl_path = SHIP / "compliance-checklist.json"
    if cl_path.is_file():
        previous_checklist = json.loads(cl_path.read_text(encoding="utf-8"))
    checklist = rebuild_checklist(corpus, pin, previous_checklist)

    dump = lambda x: json.dumps(x, indent=2) + "\n"  # noqa: E731
    outputs = {
        PIN: dump(pin),
        SHIP / "job-packet.schema.json": dump(derived_packet),
        SHIP / "evaluator-record.schema.json": dump(derived_record),
        SHIP / "audit-record.schema.json": dump(derived_audit),
        cl_path: dump(checklist),
    }
    return pin, outputs, derived_packet, checklist


def check_main(args, old_pin: dict) -> int:
    """--check: write nothing. The vendored copy always; the corpus build-check only when a corpus resolves."""
    problems = check_vendored(old_pin)
    vdir_rel = vendor_dir(old_pin).relative_to(REPO).as_posix()
    if problems:
        print(f"VENDORED COPY MISMATCH — {vdir_rel} does not match VENDOR.json / tools/pin.json:")
        for p in problems:
            print(f"  - {p}")
    else:
        n = len(json.loads((vendor_dir(old_pin) / "VENDOR.json").read_text(encoding="utf-8"))["files"])
        print(f"VENDORED OK  {vdir_rel}: {n} files match VENDOR.json; both schemas match tools/pin.json")

    try:
        required = edi_corpus.require_corpus()
        resolved = edi_corpus.resolve(args.corpus or None, CORPUS_NEED)
    except edi_corpus.CorpusUsageError as e:
        edi_corpus.usage_exit(str(e))
    if resolved is None:
        failed = edi_corpus.not_run(CHECK_ID, required, edi_corpus.NO_CORPUS)
        return 1 if (problems or failed) else 0

    resolved.announce()
    corpus = resolved.path
    corpus_problems = []
    top = git_toplevel(corpus)
    hashes = {f: sha256(corpus / f) for f in CORPUS_FILES}
    want_rel = Path(old_pin.get("path", "."))
    try:
        at_path = top is not None and corpus.resolve().relative_to(top) == want_rel
    except ValueError:
        at_path = False
    if not at_path:
        where = (f"it sits at {corpus.resolve().relative_to(top) if corpus.resolve().is_relative_to(top) else corpus} "
                 f"in a checkout whose top level is {top}" if top else "it is not inside any git checkout")
        print(f"COMMIT NOT VERIFIABLE  {resolved.given}: the corpus is not <checkout>/{want_rel.as_posix()} ({where}), "
              f"so its commit cannot be compared with the pin {old_pin['commit'][:12]}")
        corpus_problems.append("commit not verifiable")
        changed = [f for f, h in old_pin["files"].items() if hashes.get(f) != h]
        for f in changed:
            print(f"  - {f} sha256 differs from tools/pin.json")
        corpus_problems += changed
    else:
        commit = corpus_commit(corpus)
        drift = []
        if old_pin["commit"] != commit:
            drift.append(f"corpus commit {old_pin['commit'][:12]} -> {commit[:12]}")
        for f, h in old_pin["files"].items():
            if hashes.get(f) != h:
                drift.append(f"{f} changed")
        dh = doctrine_hashes(corpus)
        for f, h in old_pin.get("doctrine_files", {}).items():
            if dh.get(f) != h:
                drift.append(f"{f} changed (above the load set: re-read it)")
        if drift:
            print("DRIFT — the pin no longer matches the corpus:")
            for d in drift:
                print(f"  - {d}")
            print("Re-pin deliberately (--repin) after re-reading the changed doctrine.")
            corpus_problems += drift
        else:
            _, outputs, _, _ = derive_all(corpus, commit, hashes, coverage_state(corpus), old_pin)
            stale = [p for p, text in outputs.items()
                     if not p.is_file() or p.read_text(encoding="utf-8") != text]
            for p in stale:
                print(f"DERIVED FILE DIFFERS  {p.relative_to(REPO).as_posix()}: the committed bytes are not what "
                      f"the derivation produces from the pinned corpus (hand edit?)")
            corpus_problems += stale
            if not stale:
                print(f"PIN OK  {corpus}@{commit[:12]}  Contracts v{old_pin['coverage']['contracts_version']}; "
                      f"{len(outputs)} derived files rebuild byte-identical")

        # The vendored copy must still be the corpus's bytes (it is the corpus's, never Plumbline's).
        vdir = vendor_dir(old_pin)
        vj = vdir / "VENDOR.json"
        if vj.is_file():
            for name, entry in json.loads(vj.read_text(encoding="utf-8")).get("files", {}).items():
                src = corpus / entry.get("original_path", "")
                if not src.is_file() or (vdir / name).is_file() and src.read_bytes() != (vdir / name).read_bytes():
                    print(f"  - {(vdir / name).relative_to(REPO).as_posix()} differs from the corpus's "
                          f"{entry.get('original_path')}")
                    corpus_problems.append(name)
    edi_corpus.ran(CHECK_ID, not corpus_problems)
    return 1 if (problems or corpus_problems) else 0


# ----------------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="", help="path to <evaluatordriven/doctrine checkout>/contracts")
    ap.add_argument("--repin", action="store_true", help="re-pin to the corpus's current commit")
    ap.add_argument("--check", action="store_true", help="verify the tree matches the pin; write nothing")
    ap.add_argument("--custody", action="store_true", help="the custody/v1 pin and derived schema (no corpus needed)")
    ap.add_argument("--custody-dir", default="", help="custody checkout (default: $CUSTODY_DIR)")
    ap.add_argument("--require-upstream", action="store_true",
                    help="with --custody --check: exit 2 when no custody checkout is given, instead of a partial check")
    args = ap.parse_args()

    if args.custody:
        return custody_main(args)

    old_pin = json.loads(PIN.read_text(encoding="utf-8")) if PIN.is_file() else None
    if args.check and not old_pin:
        print("NO PIN — run without --check to establish one")
        return 1

    if args.check:
        return check_main(args, old_pin)

    resolved = resolve_corpus(args.corpus)
    if resolved is None:
        print("E-DI corpus not found: build mode needs it. Set --corpus or EDI_CORPUS (or plugins.edi-loop.corpus "
              "in the Hermes config) to <an evaluatordriven/doctrine checkout>/contracts at the pinned commit.")
        return 1
    corpus = resolved.path
    commit = corpus_commit(corpus)
    hashes = {f: sha256(corpus / f) for f in CORPUS_FILES}
    coverage = coverage_state(corpus)

    if old_pin and not args.repin:
        drift = [f for f, h in old_pin["files"].items() if hashes.get(f) != h]
        dh = doctrine_hashes(corpus)
        drift += [f for f, h in old_pin.get("doctrine_files", {}).items() if dh.get(f) != h]
        if old_pin["commit"] != commit or drift:
            print("REFUSING TO BUILD: the corpus moved since the last pin.")
            print(f"  pinned {old_pin['commit'][:12]}  current {commit[:12]}")
            for d in drift:
                print(f"  changed: {d}")
            print("Re-read the changed doctrine, then re-run with --repin.")
            return 1

    pin, outputs, derived_packet, checklist = derive_all(corpus, commit, hashes, coverage, old_pin)
    for path, text in outputs.items():
        path.write_text(text, encoding="utf-8")
    inst = json.loads(INSTANCE.read_text(encoding="utf-8"))

    print(f"pinned      {corpus}@{commit[:12]}  Contracts v{coverage['contracts_version']}")
    print(f"coverage    {coverage['counts']}")
    print(f"job-packet  {len(derived_packet.get('properties', {}))} properties, {len(derived_packet.get('allOf', []))} if/then rules (corpus + instance)")
    print(f"record      derived verbatim from the corpus §5 shape")
    print(f"audit       requires extensions: {inst['record_extension_conventions']['audit_required_extensions']}")
    print(f"checklist   {len(checklist['clauses'])} clauses §9 {checklist['clauses'][0]['id']}..{checklist['clauses'][-1]['id']}, "
          f"{checklist['provenance']['annotations_reattached']} `why` annotations re-attached, "
          f"retired reserved: {checklist['provenance']['retired_ids_reserved']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

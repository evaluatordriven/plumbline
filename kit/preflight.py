#!/usr/bin/env python3
"""Preflight before Maker — fail in seconds, not dollars.

Usage:
  PYTHONPATH=. python3 -m kit.preflight --packet path/to/packet.json --cwd worktree
  PYTHONPATH=. python3 kit/preflight.py --packet ... --cwd ...

Exit 0 = no blocking problems (warnings may still print).
Exit 2 = blocking problems (do not seat Maker until Owner accepts or fixed).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

# Allow `python3 kit/preflight.py` from repo root.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from kit.delight import (  # noqa: E402
    BUDGET_FLOOR_USD,
    budget_floor_usd,
    job_class_of,
)

BASE_COMMIT_RE = re.compile(
    r"BASE_COMMIT\s*=\s*[\"']([0-9a-fA-F]{7,40})[\"']"
)
SPEC_VERSION_RE = re.compile(r"\*\*Version\s+(\d+\.\d+\.\d+)\b")


def _read_json(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("%s is not a JSON object" % path)
    return data


def _git_head(cwd: str) -> str | None:
    import subprocess
    try:
        out = subprocess.check_output(
            ["git", "-C", cwd, "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return out.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def _bar_path(packet: dict, cwd: str) -> str | None:
    art_raw = packet.get("artifact")
    art = art_raw if isinstance(art_raw, dict) else {}
    frozen_raw = art.get("frozen")
    frozen = frozen_raw if isinstance(frozen_raw, list) else []
    for item in frozen:
        if isinstance(item, str) and item.endswith(".py") and "test_" in item:
            p = os.path.join(cwd, item)
            if os.path.isfile(p):
                return p
    gt_raw = packet.get("ground_truth")
    gt_list = gt_raw if isinstance(gt_raw, list) else []
    for gt in gt_list:
        if not isinstance(gt, dict):
            continue
        for k in ("path", "uri", "file"):
            v = gt.get(k)
            if isinstance(v, str) and v.endswith(".py"):
                p = v if os.path.isabs(v) else os.path.join(cwd, v)
                if os.path.isfile(p):
                    return p
    return None


def preflight(packet: dict, cwd: str, *, custody_tree: str | None = None) -> dict:
    """Return {blocking: [...], warnings: [...], job_class, facts: {...}}."""
    blocking: list[str] = []
    warnings: list[str] = []
    facts: dict = {}
    cwd = os.path.abspath(cwd)
    jc = job_class_of(packet)
    facts["job_class"] = jc
    facts["cwd"] = cwd
    facts["cwd_exists"] = os.path.isdir(cwd)

    if not os.path.isdir(cwd):
        blocking.append("cwd is not a directory: %s" % cwd)

    head = _git_head(cwd) if os.path.isdir(cwd) else None
    facts["head"] = head

    bar = _bar_path(packet, cwd)
    facts["bar_path"] = bar
    if bar and os.path.isfile(bar):
        try:
            text = open(bar, encoding="utf-8").read()
        except OSError as e:
            warnings.append("cannot read bar: %s" % e)
            text = ""
        m = BASE_COMMIT_RE.search(text)
        if m:
            base = m.group(1)
            facts["bar_BASE_COMMIT"] = base
            if head and not head.startswith(base) and not base.startswith(head[: len(base)]):
                if head[:7] != base[:7]:
                    blocking.append(
                        "bar BASE_COMMIT %s does not match worktree HEAD %s — "
                        "measure will lie (Job 40 pin lesson)" % (base[:12], (head or "")[:12])
                    )
        else:
            warnings.append("bar has no BASE_COMMIT = '…' constant to check against HEAD")
    else:
        warnings.append("no bar file resolved from packet frozen/ground_truth — BASE check skipped")

    bounds_raw = packet.get("bounds")
    bounds = bounds_raw if isinstance(bounds_raw, dict) else {}
    ss = bounds.get("scoring_set")
    facts["scoring_set_len"] = len(ss) if isinstance(ss, list) else None
    if packet.get("mode") == "scored" and not (isinstance(ss, list) and ss):
        warnings.append("mode scored but bounds.scoring_set missing — loop may refuse or score full bar")

    budget_raw = bounds.get("budget")
    budget = budget_raw if isinstance(budget_raw, dict) else {}
    amount = budget.get("amount")
    facts["budget_amount"] = amount
    floor = budget_floor_usd(jc)
    facts["budget_floor"] = floor
    try:
        amt_f = float(amount) if amount is not None else None
    except (TypeError, ValueError):
        amt_f = None
    if jc == "full_release_record" and (amt_f is None or amt_f < floor):
        warnings.append(
            "job_class full_release_record budget %s < floor $%.2f — hollow emit thrash risk" % (amount, floor)
        )
    elif jc in BUDGET_FLOOR_USD and amt_f is not None and floor and amt_f < floor:
        warnings.append("budget %s below soft floor $%.2f for job_class %s" % (amount, floor, jc))

    tree = custody_tree or os.environ.get("PLUMBLINE_CUSTODY") or cwd
    tree = os.path.abspath(tree)
    facts["custody_tree"] = tree
    spec = os.path.join(tree, "SPEC.md")
    if os.path.isfile(spec):
        try:
            with open(spec, encoding="utf-8") as _sf:
                lines = _sf.read().splitlines()
            ver = None
            for ln in lines[:12]:
                m = SPEC_VERSION_RE.search(ln)
                if m:
                    ver = m.group(1)
                    break
            facts["custody_SPEC_version"] = ver
            if jc == "full_release_record" and ver:
                warnings.append(
                    "emit will stamp specVersion from custody tree %s (SPEC %s) — "
                    "confirm this is the candidate tree, not a stale CI pin" % (tree, ver)
                )
        except OSError:
            warnings.append("cannot read SPEC.md under custody tree %s" % tree)
    else:
        if jc == "full_release_record":
            blocking.append("full_release_record needs a custody tree with SPEC.md; none at %s" % tree)
        else:
            warnings.append("no SPEC.md at custody tree %s" % tree)

    if packet.get("ratified") is False:
        blocking.append("packet.ratified is false — do not dispatch Maker")
    elif packet.get("ratified") is not True:
        warnings.append("packet.ratified not true — loop will refuse until Owner ratifies")

    return {
        "blocking": blocking,
        "warnings": warnings,
        "job_class": jc,
        "facts": facts,
        "ok": not blocking,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--packet", required=True, help="path to job packet JSON")
    p.add_argument("--cwd", required=True, help="work tree to measure / emit against")
    p.add_argument("--custody-tree", default=None, help="override PLUMBLINE_CUSTODY / emit SPEC tree")
    p.add_argument("--json", action="store_true", help="print full result JSON")
    args = p.parse_args(argv)
    try:
        packet = _read_json(args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print("preflight: cannot read packet: %s" % e, file=sys.stderr)
        return 2
    result = preflight(packet, args.cwd, custody_tree=args.custody_tree)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("preflight job_class=%s ok=%s" % (result["job_class"], result["ok"]))
        for k, v in (result.get("facts") or {}).items():
            print("  fact %s: %s" % (k, v))
        for w in result["warnings"]:
            print("  WARN: %s" % w)
        for b in result["blocking"]:
            print("  BLOCK: %s" % b)
        if result["ok"]:
            print("preflight: no blockers — Maker may be seated (read WARNs)")
        else:
            print("preflight: BLOCKED — fix or Owner-accept before Maker")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())

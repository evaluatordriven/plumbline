#!/usr/bin/env python3
"""Job 2026-10-28-custody-times-ledger-spend: the Maker-side test step (the same runs as bar G2, so the Maker sees
what S1 will see; this is not the evaluator). Stdlib only; no network; no model call.

  run_tests.py CHECKOUT --py PYTHON --corpus DIR --work NEW_DIR --out RESULTS.json [--base BASE_RESULTS.json]

Stages CHECKOUT's working tree (`git add -A`), records it as an unreferenced commit object on top of HEAD (`git
write-tree` + `git commit-tree`; no branch moves, nothing is committed), and clones that into NEW_DIR (must not exist;
under TMPDIR, never /tmp). So exactly the files written by extract_files.py are tested, in a clean clone, and the
Maker checkout's files are not changed by the suite. Runs every tests/*.py there with PYTHON (cwd = CHECKOUT, env EDI_CORPUS=DIR), then
`tools/build_schemas.py --check`, then records `git status --porcelain` of the clone (bar T7 wants it empty after the
suite; reported, not gated here: it is the emitter part's job and S1 checks it). Writes {name: {rc, tail}} to RESULTS.json. With --base (the same file made once on
a base checkout), exit 0 only when every base test has its base rc and every new test has rc 0; otherwise exit 1
and print, verbatim, the failing tests' output tails (the text to hand back to the Maker). Without --base: exit 0.
"""
import argparse, json, os, subprocess, sys
from pathlib import Path


def run(cmd, cwd, env):
    try:
        r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=1800)
        return r.returncode, (r.stdout + r.stderr)[-4000:]
    except subprocess.TimeoutExpired:
        return 124, "timeout after 1800 s"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("checkout"); ap.add_argument("--py", required=True); ap.add_argument("--corpus", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--base"); ap.add_argument("--work", required=True)
    a = ap.parse_args()
    w = Path(a.work).resolve()
    if w.exists() or str(w) == "/tmp" or str(w).startswith("/tmp/"):
        print(f"run_tests: --work {w} exists or is under /tmp", file=sys.stderr); return 2
    g = lambda *x: subprocess.run(["git", "-C", a.checkout, *x], capture_output=True, text=True, check=True).stdout.strip()
    g("add", "-A")
    head = g("-c", "user.name=run_tests", "-c", "user.email=run_tests@invalid", "commit-tree", g("write-tree"),
             "-p", "HEAD", "-m", "run_tests snapshot (unreferenced)")
    subprocess.run(["git", "clone", "-q", "--no-checkout", str(Path(a.checkout).resolve()), str(w)], check=True)
    subprocess.run(["git", "-C", str(w), "checkout", "-q", head], check=True)
    co = w
    env = dict(os.environ, EDI_CORPUS=a.corpus, PYTHONDONTWRITEBYTECODE="1")
    res = {}
    for t in sorted((co / "tests").glob("*.py")):
        rc, tail = run([a.py, str(t.relative_to(co))], co, env); res[t.name] = {"rc": rc, "tail": tail}
    rc, tail = run([a.py, "tools/build_schemas.py", "--check"], co, env); res["build_schemas --check"] = {"rc": rc, "tail": tail}
    por = subprocess.run(["git", "-C", str(co), "status", "--porcelain"], capture_output=True, text=True).stdout
    print(f"run_tests: tested {head}; porcelain after the suite: {'empty' if not por else repr(por[:600])}")
    Path(a.out).write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if not a.base:
        print(json.dumps({k: v["rc"] for k, v in res.items()}, sort_keys=True)); return 0
    base = json.loads(Path(a.base).read_text(encoding="utf-8"))
    bad = []
    for k, v in res.items():
        if k == "porcelain":
            continue
        want = base[k]["rc"] if k in base else 0
        if v["rc"] != want:
            bad.append((k, v, want))
    for k in base:
        if k not in res:
            bad.append((k, {"rc": None, "tail": "test file missing from the checkout"}, base[k]["rc"]))
    if not bad:
        print(f"run_tests: OK ({len(res)} runs; base results kept; new tests pass)"); return 0
    for k, v, want in bad:
        print(f"=== {k}: rc {v['rc']} (expected {want}) ===\n{v['tail']}")
    print(f"run_tests: FAILED ({len(bad)} of {len(res)})"); return 1


if __name__ == "__main__":
    sys.exit(main())

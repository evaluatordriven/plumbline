"""A re-pin moves every field of the pin, the version included.

Measured 2026-11-10 while measuring the 0.9.6 -> 0.9.8 move: `--custody --repin` rewrote `commit` and
every file digest and left `specVersion` at its old value. A pin could therefore name 0.9.8's bytes
and claim 0.9.6, which is exactly the self-contradiction the whole repository is meant to make
impossible — and nothing would have reported it, because the version is prose in the pin.

The fix reads the version from the checkout's own SPEC.md, and refuses the re-pin when it cannot.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import build_schemas  # noqa: E402

SPEC = """# Evaluator Driven — the custody record

**Version 0.9.8 · candidate · 2026-10-27** · Predicate type `https://evaluatordriven.com/custody/v1`
"""


def make_checkout(root: Path, spec: str | None) -> Path:
    (root / "schema").mkdir(parents=True)
    (root / "checker").mkdir(parents=True)
    (root / "schema" / "custody-v1.schema.json").write_text("{}\n", encoding="utf-8")
    (root / "checker" / "check.py").write_text("# checker\n", encoding="utf-8")
    if spec is not None:
        (root / "SPEC.md").write_text(spec, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.email=t@e", "-c", "user.name=t",
                    "commit", "-qm", "checkout"], check=True)
    return root


class ARepinCarriesTheVersionItPinned(unittest.TestCase):
    def test_the_spec_header_is_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(build_schemas.custody_spec_version(make_checkout(Path(tmp), SPEC)), "0.9.8")

    def test_a_repin_moves_commit_version_and_digests_together(self):
        cpin = {"source": "x", "commit": "0" * 40, "specVersion": "0.9.6",
                "files": {"schema/custody-v1.schema.json": "0" * 64, "checker/check.py": "0" * 64,
                          "SPEC.md": "0" * 64}}
        with tempfile.TemporaryDirectory() as tmp:
            out = build_schemas.repinned_custody(cpin, make_checkout(Path(tmp), SPEC))
        self.assertIsNotNone(out)
        self.assertEqual(out["specVersion"], "0.9.8")
        self.assertNotEqual(out["commit"], cpin["commit"])
        for name, digest in out["files"].items():
            self.assertNotEqual(digest, cpin["files"][name], name)

    def test_a_spec_with_no_version_refuses_the_repin(self):
        cpin = {"source": "x", "commit": "0" * 40, "specVersion": "0.9.6", "files": {}}
        with tempfile.TemporaryDirectory() as tmp:
            checkout = make_checkout(Path(tmp), "# no version here\n")
            self.assertIsNone(build_schemas.repinned_custody(cpin, checkout))

    def test_a_checkout_that_is_not_git_refuses_the_repin(self):
        cpin = {"source": "x", "commit": "0" * 40, "specVersion": "0.9.6", "files": {}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SPEC.md").write_text(SPEC, encoding="utf-8")
            self.assertIsNone(build_schemas.repinned_custody(cpin, root))

    def test_the_repository_pin_states_a_version_its_checkout_would_produce(self):
        pin = json.loads((REPO / "tools" / "pin.json").read_text(encoding="utf-8"))["custody"]
        self.assertRegex(pin["specVersion"], r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()

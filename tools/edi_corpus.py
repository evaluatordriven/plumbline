#!/usr/bin/env python3
"""One resolver for the E-DI corpus, shared by every corpus-aware entry point.

WHY ONE RESOLVER
    Before this file, each tool resolved the corpus its own way: one parsed the Hermes config with PyYAML and
    swallowed every error, one scanned it as text, one read only $EDI_CORPUS and exited, one took a positional
    argument. A bad $EDI_CORPUS fell through to the next rule, so a typo produced a silent stale reading — the
    failure the convention names. The rules below are the Owner's (D-E, D-V7) and they live here once.

THE RULES (normative; tests/test_corpus_optin.py holds them)
    PLUMBLINE_REQUIRE_CORPUS
        only the exact value "1" turns the requirement on; unset, "" or "0" leave it off; any other value
        ("true", "yes", "2", " 1", ...) is a usage error (exit 2) whose message names the variable.
    Resolution order, first rule that is SET wins and is never fallen through:
        1. --corpus PATH                                       source "--corpus"
        2. $EDI_CORPUS (unset or "" counts as not set)         source "EDI_CORPUS"
        3. plugins.edi-loop.corpus in $HERMES_HOME/config.yaml, else ~/.hermes/config.yaml
                                                               source "hermes-config <path>"
        A value that is set but is not a corpus is a usage error (exit 2) naming the path. It never falls
        through to the next rule and never falls back to the vendored copy.
    A corpus is a directory holding schemas/job-packet.schema.json, plus whatever else the calling tool needs
    (for example tools/validate_job_packet.py).
    A Hermes config that exists but cannot be read (no PyYAML, bad YAML) is REPORTED on stdout with its path and
    the reason, and the tool carries on as with no corpus. It is never ignored silently.

LINE FORMS (stdout, whole lines; tests/run_all.py reads them)
    corpus source: <src>              printed whenever a corpus resolves, never otherwise
    SKIP[corpus] <id>: <reason>       no corpus, requirement off
    RAN[corpus] <id>: pass|fail       the corpus resolved and the check ran
    FAIL[corpus] <id>: <reason>       no corpus, PLUMBLINE_REQUIRE_CORPUS=1
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

REQUIRE_VAR = "PLUMBLINE_REQUIRE_CORPUS"
CORPUS_VAR = "EDI_CORPUS"
IDS = ("corpus.battery-equality", "corpus.pin-on-disk", "corpus.audit-equality",
       "corpus.build-check", "corpus.run-cases")
BASE_NEED = ("schemas/job-packet.schema.json",)
USAGE_RC = 2


class CorpusUsageError(Exception):
    """A setting that is present but wrong. The message names the variable or the path."""


@dataclass(frozen=True)
class Corpus:
    path: Path
    source: str          # "--corpus", "EDI_CORPUS" or "hermes-config <path>"
    given: str           # the value as given, before expansion

    def announce(self) -> None:
        print(f"corpus source: {self.source}", flush=True)


def require_corpus() -> bool:
    """PLUMBLINE_REQUIRE_CORPUS, exactly as D-E states it."""
    raw = os.environ.get(REQUIRE_VAR)
    if raw is None or raw in ("", "0"):
        return False
    if raw == "1":
        return True
    raise CorpusUsageError(f"{REQUIRE_VAR}={raw!r} is not a valid value: use 1 to require the corpus, "
                           f"or leave it unset, empty or 0 (no other value is accepted)")


def hermes_config_path() -> Path:
    home = os.environ.get("HERMES_HOME")
    return (Path(home).expanduser() if home else Path.home() / ".hermes") / "config.yaml"


def _hermes_value(cfg: Path) -> str | None:
    """plugins.edi-loop.corpus (or the plugins.entries.edi-loop.settings.corpus form) from the config, or None.

    A config that exists and cannot be read is reported, with its path and the reason, never swallowed."""
    try:
        import yaml  # type: ignore
    except Exception as e:  # noqa: BLE001
        print(f"note: Hermes config {cfg} was not read: PyYAML is not importable ({type(e).__name__}: {e}); "
              f"carrying on as with no Hermes corpus", flush=True)
        return None
    try:
        doc = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
    except Exception as e:  # noqa: BLE001
        print(f"note: Hermes config {cfg} was not read: {type(e).__name__}: {' '.join(str(e).split())[:200]}; "
              f"carrying on as with no Hermes corpus", flush=True)
        return None
    plugins = doc.get("plugins") if isinstance(doc, dict) else None
    if not isinstance(plugins, dict):
        return None
    for node in (plugins.get("edi-loop"),
                 ((plugins.get("entries") or {}).get("edi-loop") or {}).get("settings")
                 if isinstance(plugins.get("entries"), dict) else None):
        if isinstance(node, dict) and node.get("corpus"):
            return str(node["corpus"])
    return None


def _check(given: str, label: str, need: tuple[str, ...]) -> Path:
    p = Path(given).expanduser()
    missing = [n for n in need if not (p / n).is_file()]
    if not p.is_dir() or missing:
        why = "does not exist or is not a directory" if not p.is_dir() else f"has no {', '.join(missing)}"
        raise CorpusUsageError(f"{label} is set to {given!r}, which is not an E-DI corpus: {p} {why}. "
                               f"A set value that is not a corpus is an error; it does not fall through to "
                               f"another rule or to the vendored copy.")
    return p.resolve()


def resolve(explicit: str | None = None, need: tuple[str, ...] = (), hermes: bool = True) -> Corpus | None:
    """The corpus, or None when no rule is set. Raises CorpusUsageError for a set value that is not a corpus."""
    need = tuple(dict.fromkeys(BASE_NEED + tuple(need)))
    if explicit is not None and explicit != "":
        return Corpus(_check(explicit, "--corpus", need), "--corpus", explicit)
    env = os.environ.get(CORPUS_VAR)
    if env:
        return Corpus(_check(env, CORPUS_VAR, need), CORPUS_VAR, env)
    if hermes:
        cfg = hermes_config_path()
        if cfg.is_file():
            val = _hermes_value(cfg)
            if val:
                return Corpus(_check(val, f"plugins.edi-loop.corpus in {cfg}", need), f"hermes-config {cfg}", val)
    return None


def resolve_or_exit(explicit: str | None = None, need: tuple[str, ...] = (), hermes: bool = True
                    ) -> tuple[Corpus | None, bool]:
    """(corpus, required) for an entry point; a usage error prints its message and exits 2.

    Announces `corpus source:` when a corpus resolves, so no caller can forget the line."""
    try:
        required = require_corpus()
        corpus = resolve(explicit, need, hermes)
    except CorpusUsageError as e:
        usage_exit(str(e))
    if corpus:
        corpus.announce()
    return corpus, required


def usage_exit(msg: str) -> "None":
    print(f"USAGE ERROR: {msg}", flush=True)
    sys.exit(USAGE_RC)


def not_run(cid: str, required: bool, reason: str) -> bool:
    """Print the line for a corpus check that cannot run. Returns True when it is a failure (required)."""
    if required:
        print(f"FAIL[corpus] {cid}: {REQUIRE_VAR}=1 requires the E-DI corpus and none resolved ({reason})",
              flush=True)
        return True
    print(f"SKIP[corpus] {cid}: {reason}", flush=True)
    return False


def ran(cid: str, ok: bool) -> None:
    print(f"RAN[corpus] {cid}: {'pass' if ok else 'fail'}", flush=True)


def no_corpus_reason(hermes: bool = True) -> str:
    rules = ("--corpus and EDI_CORPUS are unset and no readable Hermes config names a corpus" if hermes
             else "EDI_CORPUS is unset")
    return (f"no E-DI corpus resolved ({rules}); set EDI_CORPUS to a checkout of smoitozo/e-di at the "
            f"tools/pin.json commit to run it")


NO_CORPUS = no_corpus_reason(True)
NO_CORPUS_ENV = no_corpus_reason(False)

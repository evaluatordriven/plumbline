"""A release-gate building block for the conductor. It records what each arm of one turn actually did: the suite's exit and the digest of what it printed, the hashes of the frozen paths either side of the Maker, the Maker's own exit and output, and a snapshot of the working tree on both sides of the Maker. The verdict is derived from those recordings and nothing else.

These functions detect changes; they do not prevent them. Nothing here stops a file from being edited. This module is not the conductor: it does not route, apply a pass rule across a job, or persist a terminal state.
"""

from __future__ import annotations

import hashlib
import os

NOT_RECORDED = "not recorded"
MISSING = "missing"
UNREADABLE = "unreadable"
TIMEOUT = "timeout"

# The closed set of reasons a turn can carry.
NO_RED = "no RED"
FROZEN_IS_EDITABLE = "frozen test is editable"
OK = "ok"
EDIT_OUTSIDE_EDITABLE = "edit outside editable"
MAKER_FAILED = "maker failed"
NO_ARTIFACT = "no artifact"


def resolve(path: str, cwd: str | None = None) -> str:
    """The absolute, symlink-free form of ``path``, read relative to ``cwd``.

    ``cwd`` stands in for this process's directory when a turn runs in some other
    tree: "frozen.txt" with ``cwd="/tmp/job"`` is ``/tmp/job/frozen.txt``, never this
    process's own working directory. Symlinks, "." and ".." are collapsed, so two
    spellings of one file resolve to one string.
    """
    if cwd is not None and not os.path.isabs(path):
        return os.path.realpath(os.path.join(cwd, path))
    return os.path.realpath(path)


def refuse_dispatch(exit_code) -> bool:
    """True when the frozen suite exited 0: no RED, so there is nothing to dispatch."""
    return exit_code == 0


def record_red(exit_code, output: bytes | None) -> dict:
    """One arm of a turn as it was recorded: its exit and the digest of its output.

    An arm that never ran keeps ``exit`` None. An arm that printed nothing has no
    hash invented for it, in either direction.
    """
    return {"exit": exit_code, "output_sha256": _digest(output)}


def record_arm(exit_code, output: bytes | None) -> dict:
    """The same recording under the generic name, for any arm of the turn."""
    return record_red(exit_code, output)


def freeze(paths: list[str]) -> dict:
    """Map every path to the hex sha256 of its bytes, or a sentinel if it cannot be read.

    A path that is gone is ``MISSING``. A path that is a directory, or that the
    process may not read, is ``UNREADABLE``. Neither raises: the record survives.
    """
    frozen = {}
    for path in paths:
        try:
            with open(path, "rb") as handle:
                frozen[path] = hashlib.sha256(handle.read()).hexdigest()
        except FileNotFoundError:
            frozen[path] = MISSING
        except OSError:
            frozen[path] = UNREADABLE
    return frozen


def hash_moved(before: dict, after: dict) -> bool:
    """True iff any frozen path changed digest or vanished from the later freeze."""
    return any(after.get(path) != digest for path, digest in before.items())


def refuse_editable(editable: list[str], frozen: list[str]) -> bool:
    """True when an editable path and a frozen path are the same path, or one nests in the other.

    Both sides are resolved the same way first, so "tests/t.py", "./tests/t.py" and a
    symlink to it are one path, and an editable directory that holds a frozen file is
    refused as surely as the file itself. Containment is decided by path components,
    never by a string prefix.
    """
    frozen_paths = [resolve(path) for path in frozen]
    return any(
        _same_or_nested(resolve(path), held)
        for path in editable
        for held in frozen_paths
    )


def dispatch_reason(red_exit, editable: list[str], frozen: list[str], require_red: bool = True) -> str | None:
    """None when the turn may be dispatched, otherwise the reason it may not be.

    ``require_red`` False does not refuse a suite that already passed. A timeout
    and a frozen path in the editable set are still refused. The default keeps
    the published behaviour.
    """
    if red_exit == TIMEOUT:
        return TIMEOUT
    if require_red and refuse_dispatch(red_exit):
        return NO_RED
    if refuse_editable(list(editable), list(frozen)):
        return FROZEN_IS_EDITABLE
    return None


def snapshot(root: str) -> dict:
    """Map every regular file under ``root`` to the hex sha256 of its bytes right now.

    Nothing is skipped. A cache, a ``.git`` directory, and ``__pycache__`` are
    recorded like any other file. The caller decides what not to judge, by passing
    an ignore list. A file that is not a regular file is not opened, so a snapshot
    cannot block on a socket or a FIFO.
    """
    files = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(dirnames)
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "rb") as handle:
                    files[path] = hashlib.sha256(handle.read()).hexdigest()
            except FileNotFoundError:
                continue
            except OSError:
                files[path] = UNREADABLE
    return files


def changed_paths(before: dict, after: dict) -> list[str]:
    """Every path that was added, removed or rewritten between the two snapshots."""
    return sorted(
        path
        for path in set(before) | set(after)
        if before.get(path) != after.get(path)
    )


def normalize_ignore(rules) -> list[str]:
    """Each rule as components, with ``.`` dropped and no leading or trailing slash.

    ``run()`` stores this normalised form in ``ignored.rules``, not the caller's
    text. ``./.git/`` is recorded as ``.git``. Backslashes are stored as ``/``.
    """
    normalised = []
    for rule in rules:
        parts = [
            part
            for part in rule.replace("\\", "/").split("/")
            if part not in ("", ".")
        ]
        if parts:
            normalised.append("/".join(parts))
    return normalised


def matches_ignore(rel: str, rules) -> bool:
    """True when ``rel`` (relative to the turn root) matches one ignore rule.

    A rule with no slash matches that name as any path component, at any depth.
    A rule with a slash is a path relative to the turn root, matched by component
    from the start of ``rel``. Rules are normalised first, so ``./build`` and
    ``build/`` both mean ``build``.
    """
    parts = rel.replace("\\", "/").split("/")
    for rule in normalize_ignore(rules):
        if "/" not in rule:
            if rule in parts:
                return True
        else:
            rule_parts = rule.split("/")
            if parts[: len(rule_parts)] == rule_parts:
                return True
    return False


def outside_editable(changes: list[str], editable: list[str], root: str | None = None) -> list[str]:
    """The changed paths that no editable path names or contains.

    ``root`` is the tree the editable entries are relative to. Passing it is not
    optional in practice: without it a relative entry resolves against THIS
    process's directory, so the answer depends on where the loop happened to be
    started. Measured 2026-11-10 on Job 32 record-4 — one changed file, inside the
    declared set, reported outside it because the caller's directory was not the
    tree. The changes are already absolute; the editable entries are not.
    """
    base = os.path.realpath(root) if root else None
    roots = [resolve(path, base) for path in editable]
    return [
        path
        for path in changes
        if not any(_same_or_nested(resolve(path), root) for root in roots)
    ]


def is_pass(*, hashes_unchanged: bool, rerun_exit, applied_edit=False) -> bool:
    """A pass is unchanged frozen hashes and a clean rerun; nothing else enters into it.

    ``applied_edit`` is accepted so older callers keep working, and it carries no
    weight: a pass is decided by the frozen hashes and the rerun's exit, never by what
    the Maker says it applied.
    """
    return hashes_unchanged is True and rerun_exit == 0


def gate(
    frozen: dict,
    after: dict,
    editable: list[str],
    red_exit,
    red_output: bytes | None,
    rerun_exit=None,
    maker_exit=None,
    changes: list[str] | None = None,
    require_red: bool = True,
    root: str | None = None,
) -> dict:
    """Decide whether a turn counts, from the recordings it was handed.

    The frozen dict is the single representation of the frozen set: its keys are the
    frozen paths, so the editability refusal and the freeze comparison read the same
    thing. ``hashes_unchanged`` is that comparison and nothing else; what the Maker
    wrote is a separate question, answered by ``changes`` against ``editable``.

    The order is the point. A turn that was never dispatched — no RED, a frozen file
    that is also editable, a suite that timed out — records nothing further. A
    dispatched turn is judged next on whether the Maker ran at all: a timeout and a
    non-zero exit are named before anything it wrote is looked at. Only then does the
    working-tree snapshot matter, and only a turn that wrote something inside the
    editable set can reach the pass test, which needs unchanged frozen hashes and a
    clean rerun. An edit the Maker claims to have applied buys nothing here.

    A gate called without a Maker exit (``maker_exit`` is None) has no Maker to judge,
    so the artifact questions are not asked of it: only the freeze and the rerun
    speak. Every key of :func:`_verdict` is present on every path — exactly those five
    keys, no more. The Maker's and the rerun's own arms are the caller's to record:
    :func:`kit.conductor_run.run` attaches them after this call.
    """
    red = record_red(red_exit, red_output)
    hashes_unchanged = not hash_moved(frozen, after)

    refusal = dispatch_reason(red_exit, editable, list(frozen), require_red)
    if refusal is not None:
        return _verdict(False, refusal, red, hashes_unchanged)

    if maker_exit is None:
        if rerun_exit == TIMEOUT:
            return _verdict(True, TIMEOUT, red, hashes_unchanged)
        passed = is_pass(hashes_unchanged=hashes_unchanged, rerun_exit=rerun_exit)
        return _verdict(True, OK, red, hashes_unchanged, passed=passed)

    if maker_exit == TIMEOUT:
        return _verdict(True, TIMEOUT, red, hashes_unchanged)
    if maker_exit != 0:
        return _verdict(True, MAKER_FAILED, red, hashes_unchanged)
    if outside_editable(changes or [], editable, root):
        return _verdict(True, EDIT_OUTSIDE_EDITABLE, red, hashes_unchanged)
    if not changes:
        return _verdict(True, NO_ARTIFACT, red, hashes_unchanged)
    if rerun_exit == TIMEOUT:
        return _verdict(True, TIMEOUT, red, hashes_unchanged)

    passed = is_pass(hashes_unchanged=hashes_unchanged, rerun_exit=rerun_exit)
    return _verdict(True, OK, red, hashes_unchanged, passed=passed)


def record_field(value) -> str:
    """The value as a string, or "not recorded" when it was absent or blank."""
    if value is None or str(value).strip() == "":
        return NOT_RECORDED
    return str(value)


def _verdict(
    dispatched: bool,
    reason: str,
    red: dict,
    hashes_unchanged: bool,
    passed: bool = False,
) -> dict:
    """One shape for every verdict, so a caller can read any path the same way."""
    return {
        "dispatched": bool(dispatched),
        "reason": reason,
        "passed": bool(passed),
        "red": red,
        "hashes_unchanged": hashes_unchanged,
    }


def _same_or_nested(a: str, b: str) -> bool:
    """True when ``a`` and ``b`` are the same path, or one contains the other."""
    if a == b:
        return True
    try:
        common = os.path.commonpath([a, b])
    except ValueError:  # no path in common at all (mixed drives on Windows)
        return False
    return common == a or common == b


def _digest(output: bytes | None) -> str:
    if not output:
        return NOT_RECORDED
    return hashlib.sha256(output).hexdigest()

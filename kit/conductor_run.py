"""Sequence one turn for the release-gate building block.

This module runs the commands and hands the bytes to
:mod:`kit.conductor_software`. It is not the conductor.

The order is the point: the suite is run first and its real exit and real output are
what the gate sees as the RED. The freeze and the first snapshot happen after that
run and before the Maker, the same full list is frozen and the tree is snapshotted
again afterwards, and the rerun closes the loop. A Maker that prints "Applied edit"
buys nothing here.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time

try:  # imported as part of the kit package
    from . import conductor_software
except ImportError:  # imported as a top-level module
    import conductor_software  # type: ignore[no-redef]


_POSIX = os.name == "posix"

# A caller who omits the bound still cannot hang forever. A real Maker run
# passes its own timeout_s. Six hundred seconds is the floor the maintainer set.
DEFAULT_TIMEOUT_S = 600


def run(
    test_cmd: list[str],
    freeze_paths: list[str],
    editable: list[str],
    maker_cmd: list[str],
    commit=None,
    cwd: str | None = None,
    timeout_s: float | None = DEFAULT_TIMEOUT_S,
    ignore: list[str] | None = None,
    require_red: bool = True,
    maker_env: dict | None = None,
    await_exit_file: str | None = None,
    await_dispatch_file: str | None = None,
) -> dict:
    """Run one turn and return the gate's verdict plus the recorded arms and commit.

    ``cwd`` is the tree the turn happens in, and it is also what every relative
    ``freeze_paths`` and ``editable`` entry is read against — never this process's
    directory when a turn names another. ``timeout_s`` bounds each command. The
    default is six hundred seconds, so a caller who forgets the bound does not hang,
    and an ordinary suite is not refused for being slower than two seconds.
    Pass ``None`` to leave a command unbounded. A library caller should not.
    ``ignore`` names paths the snapshot still records but does not judge. A rule
    with no slash matches that name as any path component. Ignoring ``__pycache__``
    re-opens the bytecode plant: the planted ``.pyc`` is listed in ``ignored.paths``
    and is not a reason to refuse. ``ignored.rules`` records each rule normalised
    (``./.git/`` is recorded as ``.git``), not the caller's text. Backslashes are
    stored as ``/``. In a git checkout you will usually want
    ``ignore=[".git"]``: an honest Maker that runs ``git status`` or ``git add``
    rewrites ``.git/index`` and is otherwise flagged.

    This detects; it is not a sandbox. Only files under ``cwd`` are watched: writes
    outside it, including through symlinks inside it, are not seen. A file outside
    the editable set that is unreadable both before and after a turn is recorded
    as ``unreadable`` both times. A Maker that makes it readable, edits it, and
    makes it unreadable again changes it unseen. This detects; it is not a sandbox.

    ``test_cmd`` is run first and its exit and combined output are kept verbatim: an
    empty output stays empty, and no hash is invented for it. The frozen paths and the
    working tree are then recorded as they stand. Dispatch is refused when that first
    exit was 0 (there is no RED to fix), when it was a timeout, and when an editable
    path is also a frozen one; only otherwise does ``maker_cmd`` run, and neither its
    output nor any claim it prints is a verdict. The frozen list is hashed again and
    so is the tree, the same ``test_cmd`` is run again, and the recordings go to
    :func:`kit.conductor_software.gate`, which decides. The last word on ``passed`` is
    the gate's, not this function's.

    The gate's verdict names only the five keys it is responsible for. The Maker's own
    arm, the rerun's arm and the commit are recorded here, after the gate call, onto
    the same dict — so a caller reads one record with every arm on every path, whether
    the turn was dispatched or not.
    """
    root = os.path.realpath(cwd) if cwd is not None else os.path.realpath(os.getcwd())
    rules = conductor_software.normalize_ignore(list(ignore or []))

    # A frozen path that is absent, a directory, or unreadable is a caller error,
    # not a turn: refuse before the RED run so nothing is dispatched.
    bad = []
    for path in freeze_paths:
        resolved = conductor_software.resolve(path, root)
        if not os.path.exists(resolved):
            bad.append(path + " (missing)")
        elif not os.path.isfile(resolved):
            bad.append(path + " (not a file)")
        elif not os.access(resolved, os.R_OK):
            bad.append(path + " (unreadable)")
    if bad:
        raise ValueError("frozen path unusable at start: " + ", ".join(bad))

    frozen_paths = [conductor_software.resolve(path, root) for path in freeze_paths]

    # An ignore rule that covers a frozen path would let that path move unjudged.
    for path in frozen_paths:
        rel = os.path.relpath(path, root)
        if conductor_software.matches_ignore(rel, rules):
            raise ValueError("ignore rule covers a frozen path: " + rel)

    editable_paths = [conductor_software.resolve(path, root) for path in editable]

    red_exit, red_output = _run(test_cmd, root, timeout_s)
    frozen = conductor_software.freeze(frozen_paths)
    before = conductor_software.snapshot(root)

    dispatched = (
        conductor_software.dispatch_reason(
            red_exit, editable_paths, frozen_paths, require_red
        )
        is None
    )

    maker_exit = None
    maker_output = None
    changes: list[str] = []
    waited = None
    if dispatched:
        env = None
        if maker_env is not None:
            env = os.environ.copy()
            env.update({str(key): str(value) for key, value in maker_env.items()})
        maker_exit, maker_output = _run(maker_cmd, root, timeout_s, env=env)
        waited = _await_engine(await_exit_file, await_dispatch_file, timeout_s)
        changes = conductor_software.changed_paths(
            before, conductor_software.snapshot(root)
        )
    judged = []
    ignored_paths = []
    for path in changes:
        rel = os.path.relpath(path, root)
        if conductor_software.matches_ignore(rel, rules):
            ignored_paths.append(rel.replace(os.sep, "/"))
        else:
            judged.append(path)
    ignored = {"rules": rules, "paths": sorted(ignored_paths)}

    after = conductor_software.freeze(frozen_paths)

    rerun_exit = None
    rerun_output = None
    if dispatched:
        rerun_exit, rerun_output = _run(test_cmd, root, timeout_s)

    result = conductor_software.gate(
        frozen=frozen,
        after=after,
        editable=editable_paths,
        red_exit=red_exit,
        red_output=red_output,
        rerun_exit=rerun_exit,
        maker_exit=maker_exit,
        changes=judged,
        require_red=require_red,
        root=root,
    )
    # A scope verdict must be auditable. Measured 2026-11-10, Job 32 record-4: the
    # round said "edit outside editable" and named no path, so neither the
    # Orchestrator nor the Owner could tell whether the Maker had written outside
    # its set or the check had resolved its two sides against different bases.
    # Every judged path is recorded in the round, relative to the tree.
    result["changes"] = [os.path.relpath(path, root) for path in judged]
    result["editable"] = [os.path.relpath(path, root) for path in editable_paths]
    result["maker"] = conductor_software.record_arm(maker_exit, maker_output)
    result["rerun"] = conductor_software.record_arm(rerun_exit, rerun_output)
    result["ignored"] = ignored
    result["commit"] = conductor_software.record_field(commit)
    result["awaited_engine"] = waited
    return result


def _await_engine(exit_file: str | None, dispatch_file: str | None, timeout_s: float | None) -> dict | None:
    """Wait for a detached Maker engine's own exit record before the tree is measured.

    ``route-maker`` puts the engine in its own session and exits 0 as soon as it has
    detached, so ``_run(maker_cmd, ...)`` returns while the engine is still writing.
    Measuring there reads a tree the Maker has not finished with: measured 2026-11-09 on
    Job 31, the loop declared ``no artifact`` at 21:58:43 and the engine wrote its exit
    record ``{"exit": 0}`` and a +16/-6 diff at 21:59:39 — a real fix recorded as no work
    at all. The wait is only for a route that detached (a dispatch file exists); a route
    that ran in the foreground has already finished and is not delayed. The bound is the
    turn's own timeout, so a stalled engine still cannot outlive the packet.
    """
    if not exit_file or not dispatch_file or not os.path.isfile(dispatch_file):
        return None
    if os.path.isfile(exit_file):
        return {"waited": False, "seconds": 0.0, "reason": "exit record already written"}
    started = time.monotonic()
    while time.monotonic() - started < (timeout_s if timeout_s is not None else DEFAULT_TIMEOUT_S):
        time.sleep(0.25)
        if os.path.isfile(exit_file):
            return {"waited": True, "seconds": round(time.monotonic() - started, 3),
                    "reason": "engine exit record appeared"}
    return {"waited": True, "seconds": round(time.monotonic() - started, 3),
            "reason": "engine exit record never appeared within the turn's timeout"}


def _run(cmd: list[str], cwd: str, timeout_s: float | None, env: dict | None = None) -> tuple[int | str, bytes]:
    """Run an argv list with no shell and return (exit code, combined output).

    A command that outlives ``timeout_s`` is killed along with anything it spawned,
    and reported as the exit "timeout" rather than raised. A command that starts
    its own session leaves the process group and is not killed; this is not a sandbox.
    """
    process = subprocess.Popen(
        list(cmd),
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=_POSIX,
        env=env,
    )
    try:
        output, _ = process.communicate(timeout=timeout_s)
        return process.returncode, output
    except subprocess.TimeoutExpired:
        _kill(process)
        output, _ = process.communicate()
        return conductor_software.TIMEOUT, output


def _kill(process: subprocess.Popen) -> None:
    """Kill the whole process group, so children of the command do not linger."""
    if _POSIX:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            return
        except (ProcessLookupError, PermissionError):
            pass
    process.kill()

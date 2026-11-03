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
    and is not a reason to refuse.

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
    rules = list(ignore or [])
    missing = [
        path for path in freeze_paths
        if not os.path.exists(conductor_software.resolve(path, root))
    ]
    if missing:
        raise ValueError("frozen path missing at start: " + ", ".join(missing))
    frozen_paths = [conductor_software.resolve(path, root) for path in freeze_paths]
    editable_paths = [conductor_software.resolve(path, root) for path in editable]

    red_exit, red_output = _run(test_cmd, root, timeout_s)
    frozen = conductor_software.freeze(frozen_paths)
    before = conductor_software.snapshot(root)

    dispatched = (
        conductor_software.dispatch_reason(red_exit, editable_paths, frozen_paths)
        is None
    )

    maker_exit = None
    maker_output = None
    changes: list[str] = []
    if dispatched:
        maker_exit, maker_output = _run(maker_cmd, root, timeout_s)
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
    )
    result["maker"] = conductor_software.record_arm(maker_exit, maker_output)
    result["rerun"] = conductor_software.record_arm(rerun_exit, rerun_output)
    result["ignored"] = ignored
    result["commit"] = conductor_software.record_field(commit)
    return result


def _run(cmd: list[str], cwd: str, timeout_s: float | None) -> tuple[int | str, bytes]:
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

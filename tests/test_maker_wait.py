"""A detached Maker engine is waited for, not sampled.

Measured 2026-11-09 on Job 31 record-3: ``route-maker`` puts the engine in its own
session and exits 0 the moment it detaches, so ``loop()`` measured the work tree
while the Maker was still writing. It recorded ``no artifact`` at 21:58:43; the
engine wrote ``{"exit": 0}`` and a +16/-6 diff to the target at 21:59:39. A real
fix was booked as no work at all, at $0.02 of the packet's budget.

The control below is the old behaviour: the same maker, the same tree, measured
without waiting — and it sees nothing. The case after it waits on the engine's own
exit record and sees the change.
"""
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from kit import conductor_run  # noqa: E402

BAR = "import sys\nsys.exit(1)\n"

MAKER = textwrap.dedent(
    """
    import os, subprocess, sys
    rec, work = sys.argv[1], sys.argv[2]
    open(os.path.join(rec, "aider-dispatch.json"), "w").write("{}")
    # The engine runs detached: the route returns 0 while the work is still being written.
    child = "import os, time" + chr(10)
    child += "time.sleep(1.0)" + chr(10)
    child += "open(os.path.join(%r, 'target.py'), 'w').write('# fixed by the engine' + chr(10))" % work + chr(10)
    child += "open(os.path.join(%r, 'aider-exit.json'), 'w').write('0' + chr(10))" % rec + chr(10)
    # Detached exactly as route-maker detaches: no inherited pipes, so the caller's
    # communicate() returns on its own EOF instead of waiting for the engine.
    subprocess.Popen([sys.executable, "-c", child], start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
    sys.exit(0)
    """
)


class DetachedEngineWaitTest(unittest.TestCase):
    def test_control_measuring_immediately_misses_the_maker(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = os.path.join(tmp, "work")
            rec = os.path.join(tmp, "record")
            os.makedirs(work)
            os.makedirs(rec)
            open(os.path.join(work, "target.py"), "w").write("# base\n")
            open(os.path.join(work, "bar.py"), "w").write(BAR)
            maker = os.path.join(tmp, "maker.py")
            open(maker, "w").write(MAKER)

            result = conductor_run.run(
                test_cmd=[sys.executable, "bar.py"],
                freeze_paths=["bar.py"],
                editable=["target.py"],
                maker_cmd=[sys.executable, maker, rec, work],
                cwd=work,
                timeout_s=30,
            )
            # No await: the engine has not written yet, so the turn looks empty.
            self.assertEqual(result.get("reason"), "no artifact",
                             "the control did not reproduce the race: %r" % (result.get("reason"),))
            self.assertIsNone(result.get("awaited_engine"))

    def test_the_engine_exit_record_is_waited_for_before_measuring(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = os.path.join(tmp, "work")
            rec = os.path.join(tmp, "record")
            os.makedirs(work)
            os.makedirs(rec)
            open(os.path.join(work, "target.py"), "w").write("# base\n")
            open(os.path.join(work, "bar.py"), "w").write(BAR)
            maker = os.path.join(tmp, "maker.py")
            open(maker, "w").write(MAKER)

            result = conductor_run.run(
                test_cmd=[sys.executable, "bar.py"],
                freeze_paths=["bar.py"],
                editable=["target.py"],
                maker_cmd=[sys.executable, maker, rec, work],
                cwd=work,
                timeout_s=30,
                await_exit_file=os.path.join(rec, "aider-exit.json"),
                await_dispatch_file=os.path.join(rec, "aider-dispatch.json"),
            )
            waited = result.get("awaited_engine") or {}
            self.assertTrue(waited.get("waited"), "the loop did not wait for the engine: %r" % (waited,))
            self.assertNotEqual(result.get("reason"), "no artifact",
                                "the waited turn still saw no artifact")
            self.assertEqual(open(os.path.join(work, "target.py")).read(), "# fixed by the engine\n")


if __name__ == "__main__":
    unittest.main()

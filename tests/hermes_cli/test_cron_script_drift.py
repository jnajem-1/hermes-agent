"""``hermes cron doctor`` surfaces script drift: code changed after the last verified run.

A script-mode job proves itself only by running. Editing the wrapper (or the program it shells out
to) after the last green fire leaves the job untested, and the fleet finds out at the scheduled hour.
Drift is reported as a NOTE: the job is healthy, so it must never flip the doctor exit code.
"""

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hermes_cli.cron import _script_drift_note


def _job(last_run_at: str, script: str) -> dict:
    return {"id": "job1", "name": "test job", "script": script, "last_run_at": last_run_at}


def _iso(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) - delta).isoformat()


def test_no_note_when_script_predates_the_last_run(tmp_path):
    script = tmp_path / "wrapped.py"
    script.write_text("print('hi')\n", encoding="utf-8")
    old = time.time() - 3600
    os.utime(script, (old, old))

    assert _script_drift_note(_job(_iso(timedelta(minutes=5)), str(script)), str(script)) is None


def test_note_when_script_changed_after_the_last_run(tmp_path):
    script = tmp_path / "wrapped.py"
    script.write_text("print('edited')\n", encoding="utf-8")

    note = _script_drift_note(_job(_iso(timedelta(hours=2)), str(script)), str(script))

    assert note and "wrapped.py" in note and "first test" in note


def test_note_when_the_program_a_wrapper_runs_is_newer(tmp_path):
    target = tmp_path / "real_work.py"
    target.write_text("print('work')\n", encoding="utf-8")
    wrapper = tmp_path / "wrapper.py"
    wrapper.write_text(f'TARGET = r"{target}"\n', encoding="utf-8")
    old = time.time() - 7200
    os.utime(wrapper, (old, old))

    note = _script_drift_note(_job(_iso(timedelta(hours=3)), str(wrapper)), str(wrapper))

    assert note and "real_work.py" in note


def test_no_note_without_a_previous_run(tmp_path):
    script = tmp_path / "wrapped.py"
    script.write_text("print('hi')\n", encoding="utf-8")

    assert _script_drift_note(_job("", str(script)), str(script)) is None


def test_missing_script_is_left_to_the_issue_check(tmp_path):
    missing = Path(tmp_path) / "gone.py"

    assert _script_drift_note(_job(_iso(timedelta(hours=1)), str(missing)), str(missing)) is None

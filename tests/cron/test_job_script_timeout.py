"""Per-job ``script_timeout`` overrides the global cron script ceiling.

Motivation: one slow script (a multi-GB SQLite dump) needs headroom that the rest of the fleet
should not inherit. Before this the only knobs were env and config, both global.
"""

import pytest

from cron import jobs
from cron.jobs_time import normalize_script_timeout
from cron.scheduler_script import _get_script_timeout


def test_normalize_accepts_seconds_and_strings():
    assert normalize_script_timeout(600) == 600
    assert normalize_script_timeout("600") == 600
    assert normalize_script_timeout(None) is None
    assert normalize_script_timeout("") is None


@pytest.mark.parametrize("bad", [0, -5, True, False, "abc", 1.5, {"a": 1}])
def test_normalize_rejects_unusable_values(bad):
    with pytest.raises(ValueError):
        normalize_script_timeout(bad)


def test_job_value_wins_over_global_default():
    job = {"id": "abc", "script_timeout": 900}

    assert _get_script_timeout(job) == 900


def test_missing_job_value_falls_back_to_global():
    # With no per-job value the resolver ignores the job dict entirely: identical to no job at all.
    assert _get_script_timeout(None) == _get_script_timeout({})
    assert _get_script_timeout({"id": "abc"}) == _get_script_timeout(None)


def test_invalid_stored_value_does_not_crash_the_run():
    """A hand-edited jobs.json must degrade to the global knob, never raise mid-dispatch."""
    assert _get_script_timeout({"id": "abc", "script_timeout": "not-a-number"}) >= 1


def test_create_job_persists_a_per_job_ceiling(tmp_path):
    with jobs.use_cron_store(tmp_path):
        job = jobs.create_job(prompt="dump", schedule="every 6h", script="dump.py",
                              script_timeout="900")
        assert job["script_timeout"] == 900
        # Survives the store round-trip, which is what the resolver actually reads.
        assert jobs.get_job(job["id"])["script_timeout"] == 900


def test_create_job_refuses_an_unusable_ceiling(tmp_path):
    with jobs.use_cron_store(tmp_path):
        with pytest.raises(ValueError):
            jobs.create_job(prompt="dump", schedule="every 6h", script="dump.py",
                            script_timeout=0)


def test_update_job_sets_and_clears_the_ceiling(tmp_path):
    with jobs.use_cron_store(tmp_path):
        job = jobs.create_job(prompt="dump", schedule="every 6h", script="dump.py")
        jobs.update_job(job["id"], {"script_timeout": 120})
        assert jobs.get_job(job["id"])["script_timeout"] == 120
        jobs.update_job(job["id"], {"script_timeout": None})
        assert jobs.get_job(job["id"]).get("script_timeout") is None

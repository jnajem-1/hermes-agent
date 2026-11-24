"""Self-continuity must not call an undelivered note "already reported".

``context_from: self`` injects the previous run's answer so the job can avoid repeating
itself. That premise is false when the previous send failed: the user never saw the note,
yet the next run is told to treat it as said. The ledger already records ``delivery_outcome``
per attempt, so the intro is chosen from what actually happened rather than assumed.
"""

import sys
from pathlib import Path

import pytest

import cron.scheduler
import cron.scheduler_prompt as prompt_mod

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def cron_env(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "cron" / "output").mkdir(parents=True)

    import cron.jobs as jobs_mod
    monkeypatch.setattr(jobs_mod, "HERMES_DIR", hermes_home)
    monkeypatch.setattr(jobs_mod, "CRON_DIR", hermes_home / "cron")
    monkeypatch.setattr(jobs_mod, "JOBS_FILE", hermes_home / "cron" / "jobs.json")
    monkeypatch.setattr(jobs_mod, "OUTPUT_DIR", hermes_home / "cron" / "output")
    return hermes_home


def _write_archive(job_id: str, filename: str, answer: str) -> None:
    from cron.jobs import OUTPUT_DIR

    out_dir = OUTPUT_DIR / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / filename).write_text(
        f"# Cron Job: probe\n\n## Prompt\n\ncheck the inbox\n\n## Response\n\n{answer}\n",
        encoding="utf-8",
    )


def _ledger(monkeypatch, rows):
    import cron.executions as executions
    monkeypatch.setattr(executions, "list_executions",
                        lambda **kwargs: rows, raising=True)


class TestDeliveryGatedContinuity:
    def test_failed_delivery_marks_the_answer_unreported(self, cron_env, monkeypatch):
        from cron.jobs import create_job

        job = create_job(prompt="Report", schedule="0 8 * * *", context_from="self")
        _write_archive(job["id"], "2026-09-19_08-00-05.md", "YESTERDAY-NOTE")
        # The archive is written seconds after the attempt was claimed; the match is minute-level.
        _ledger(monkeypatch, [{
            "job_id": job["id"], "claimed_at": "2026-09-19T08:00:00-07:00",
            "status": "completed", "delivery_outcome": "failed",
        }])

        prompt, injected = prompt_mod._inject_context_from(job, "Report")

        assert injected is True
        assert "YESTERDAY-NOTE" in prompt
        assert "delivery failed" in prompt
        assert "avoid repeating what was already reported" not in prompt

    def test_a_delivered_run_keeps_the_ordinary_intro(self, cron_env, monkeypatch):
        from cron.jobs import create_job

        job = create_job(prompt="Report", schedule="0 8 * * *", context_from="self")
        _write_archive(job["id"], "2026-09-19_08-00-05.md", "YESTERDAY-NOTE")
        _ledger(monkeypatch, [{
            "job_id": job["id"], "claimed_at": "2026-09-19T08:00:00-07:00",
            "status": "completed", "delivery_outcome": "delivered",
        }])

        prompt, _ = prompt_mod._inject_context_from(job, "Report")

        assert "avoid repeating what was already reported" in prompt

    def test_a_failure_from_another_run_does_not_change_this_intro(self, cron_env, monkeypatch):
        from cron.jobs import create_job

        job = create_job(prompt="Report", schedule="0 8 * * *", context_from="self")
        _write_archive(job["id"], "2026-09-19_08-00-05.md", "YESTERDAY-NOTE")
        # Failure belongs to a different attempt six hours earlier.
        _ledger(monkeypatch, [{
            "job_id": job["id"], "claimed_at": "2026-09-19T02:00:00-07:00",
            "status": "completed", "delivery_outcome": "failed",
        }])

        prompt, _ = prompt_mod._inject_context_from(job, "Report")

        assert "avoid repeating what was already reported" in prompt

    def test_an_unreadable_ledger_fails_open(self, cron_env, monkeypatch):
        from cron.jobs import create_job
        import cron.executions as executions

        job = create_job(prompt="Report", schedule="0 8 * * *", context_from="self")
        _write_archive(job["id"], "2026-09-19_08-00-05.md", "YESTERDAY-NOTE")

        def boom(**kwargs):
            raise OSError("ledger unavailable")

        monkeypatch.setattr(executions, "list_executions", boom)

        prompt, injected = prompt_mod._inject_context_from(job, "Report")

        assert injected is True
        assert "YESTERDAY-NOTE" in prompt
        assert "avoid repeating what was already reported" in prompt

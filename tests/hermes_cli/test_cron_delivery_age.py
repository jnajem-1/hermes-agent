"""A sticky delivery failure must not read as this run's failure.

``last_delivery_error`` now survives suppressed runs, so it can be much older than the run
being displayed. The CLI list appends the age in that case and stays silent when the failure
belongs to the run on screen.
"""

from datetime import datetime, timedelta

from hermes_cli.cli_cron_lines import _stale_delivery_age


def _iso(delta: timedelta) -> str:
    return (datetime.now().astimezone() + delta).isoformat(timespec="seconds")


class TestStaleDeliveryAge:
    def test_same_run_shows_no_age(self):
        ran = _iso(timedelta(minutes=-1))
        assert _stale_delivery_age(ran, ran) == ""

    def test_older_failure_carries_its_age(self):
        stamp = _iso(timedelta(days=-3))
        rendered = _stale_delivery_age(stamp, _iso(timedelta(minutes=-1)))
        assert rendered.startswith(" (")
        assert rendered.endswith(")")

    def test_a_missing_stamp_is_not_an_error(self):
        assert _stale_delivery_age(None, _iso(timedelta()) ) == ""
        assert _stale_delivery_age(_iso(timedelta(days=-1)), None) == ""

    def test_a_corrupt_stamp_is_ignored(self):
        assert _stale_delivery_age("not-a-date", _iso(timedelta())) == ""

    def test_a_failure_from_the_previous_run_is_aged(self):
        # Last run at 09:00 today, failure recorded yesterday 21:00 → sticky, so age shows.
        ran = datetime.now().astimezone().replace(hour=9, minute=0, second=0, microsecond=0)
        failed = ran - timedelta(hours=12)
        assert _stale_delivery_age(failed.isoformat(), ran.isoformat()) != ""

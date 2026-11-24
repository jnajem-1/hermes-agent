"""Storage interface handles for fake authorities: opened on a profile home, closed after each test.

A test module activates the closing fixture by importing ``close_storage_handles`` beside
``storage_handle``.

Inline temp homes must be produced by :func:`temp_home`, never by ``tempfile.TemporaryDirectory``
directly: the closing fixture runs *after* the test body, so a ``with`` block inside the body has
already tried to delete ``state.db`` while the handle still held it. On Windows that delete fails
with ``PermissionError: [WinError 32]`` even though the test's assertions passed.
"""
import contextlib
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

_HANDLES = []


@pytest.fixture(autouse=True)
def close_storage_handles():
    yield
    while _HANDLES:
        try:
            _HANDLES.pop().close()
        except Exception:  # already closed by temp_home; closing twice is not a failure
            pass


def storage_handle(home):
    """A storage interface handle on *home*'s state.db, closed after the test."""
    from persistence_assembly import open_persistence, profile_scope
    _HANDLES.append(open_persistence(profile_scope(home=home)))
    return _HANDLES[-1]


@contextlib.contextmanager
def temp_home() -> Iterator[Path]:
    """A temporary profile home whose stores are closed *before* the directory is removed.

    Deleting a home this process still holds open fails on Windows, so the stores opened under it
    are swept on the way out. Handles stay in ``_HANDLES``; the closing fixture tolerates the
    double close.
    """
    from persistence_assembly import close_stores_under

    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        try:
            yield home
        finally:
            close_stores_under(home)

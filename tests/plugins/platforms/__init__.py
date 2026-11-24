"""Marks this directory as a package.

Without this file pytest treats every module here as top-level and puts ``tests/plugins/platforms``
on ``sys.path``, which makes the sibling ``telegram/`` directory resolve as a namespace package:
``pytest.importorskip("telegram")`` then passes vacuously and the real python-telegram-bot import
fails later with ``No module named 'telegram.error'``. As a package the directory is imported as
``tests.plugins.platforms.<module>`` and only ``tests/`` reaches ``sys.path``.
"""

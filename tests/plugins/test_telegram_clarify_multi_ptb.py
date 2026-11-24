"""Multi-select clarify toggles against the installed PTB request stack (only the transport is fake)."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
_telegram_pkg = pytest.importorskip("telegram.request", reason="python-telegram-bot not installed")
if not getattr(__import__("sys").modules.get("telegram"), "__file__", None):
    # Another test directory installs a bare ``sys.modules["telegram"]`` stub for gateway tests. Without this
    # guard the stub satisfies importorskip, these cases run against a fake PTB, and every one of them fails.
    pytest.skip("'telegram' resolves to a test stub, not python-telegram-bot", allow_module_level=True)
# A bare "telegram" is not enough: pytest inserts tests/plugins/platforms on sys.path to import
# its own modules, and the sibling ./telegram/ test directory then resolves as a namespace
# package, so the guard passes and the real submodule imports below fail at collection.
import httpx
from telegram import Bot
from telegram.request import HTTPXRequest

from gateway.config import PlatformConfig
from plugins.platforms.telegram.adapter import TelegramAdapter
from plugins.platforms.telegram.telegram_clarify_binding import ClarifyPrompt
from tools import clarify_gateway as cm


class _RefusedTransport(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request):
        raise httpx.ConnectError("connection refused", request=request)


async def _tap(adapter, msg, data, edit=None):
    query = AsyncMock(data=data, message=msg, from_user=MagicMock(id="777", first_name="Tester"))
    if edit is not None:
        query.edit_message_reply_markup.side_effect = edit
    with patch.dict(os.environ, {"TELEGRAM_ALLOWED_USERS": "*"}, clear=False):
        await adapter._handle_callback_query(MagicMock(callback_query=query), MagicMock())
    return query


@pytest.mark.asyncio
async def test_toggle_edit_that_never_left_is_not_selected():
    """A connect failure means the card still shows the old ticks, so Send must not submit the pick."""
    cm.clear_session("sk-ptb")
    adapter = TelegramAdapter(PlatformConfig(enabled=True, token="123:fake", extra={}))
    adapter._bot, adapter._app = AsyncMock(), MagicMock()
    msg = MagicMock(chat_id=12345, message_id=555, text="Pick")
    msg.chat.type = "private"
    adapter._clarify_state["cidP"] = ClarifyPrompt.from_sent("sk-ptb", msg)
    entry = cm.register("cidP", "sk-ptb", "Pick", ["red", "green"], multi_select=True)
    bot = Bot("123:fake", request=HTTPXRequest(httpx_kwargs={"transport": _RefusedTransport()}))

    async def refused_edit(**kwargs):
        return await bot.edit_message_reply_markup(chat_id=12345, message_id=555, **kwargs)

    try:
        query = await _tap(adapter, msg, "cl:cidP:t0", edit=refused_edit)
        assert adapter._clarify_multi.get("cidP", set()) == set()
        assert "Selected" not in query.answer.call_args.kwargs.get("text", "")
        await _tap(adapter, msg, "cl:cidP:go")
        assert entry.response is None and not entry.event.is_set()
    finally:
        cm.clear_session("sk-ptb")

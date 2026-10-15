"""공통 명령어 핸들러 테스트."""

from __future__ import annotations

import time

from app.handlers import common
from tests.factories import make_context, make_message_update


def _sent_text(update) -> str:
    bot = update.get_bot()
    bot.send_message.assert_awaited_once()
    return bot.send_message.await_args.kwargs["text"]


async def test_start_인사말에_이름과_도움말_안내():
    update = make_message_update("/start", first_name="철수")
    await common.cmd_start(update, make_context())
    text = _sent_text(update)
    assert "철수" in text
    assert "/help" in text


async def test_help_명령어_목록():
    update = make_message_update("/help")
    await common.cmd_help(update, make_context())
    text = _sent_text(update)
    for command in ("/start", "/help", "/status", "/id"):
        assert command in text


async def test_help_커스텀_help_text_우선():
    update = make_message_update("/help")
    context = make_context(bot_data={"help_text": "/price - 시세 조회"})
    await common.cmd_help(update, context)
    assert _sent_text(update) == "/price - 시세 조회"


async def test_id_chat_id_표시():
    update = make_message_update("/id", chat_id=777)
    await common.cmd_id(update, make_context())
    assert "777" in _sent_text(update)


async def test_status_db_연결됨_표시():
    update = make_message_update("/status")
    context = make_context(bot_data={"started_at": time.time() - 3600, "db": object()})
    await common.cmd_status(update, context)
    text = _sent_text(update)
    assert "정상 가동" in text
    assert "1시간" in text
    assert "연결됨" in text


async def test_status_db_없으면_없음_표시():
    update = make_message_update("/status")
    context = make_context(bot_data={"started_at": time.time()})
    await common.cmd_status(update, context)
    assert "없음" in _sent_text(update)


def test_format_uptime():
    assert common.format_uptime(5) == "0분 5초"
    assert common.format_uptime(65) == "1분 5초"
    assert common.format_uptime(3665) == "1시간 1분 5초"
    assert common.format_uptime(90061) == "1일 1시간 1분 1초"

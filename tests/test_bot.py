"""Application 팩토리와 오류 핸들러 테스트."""

from __future__ import annotations

from app.bot import build_application, on_error
from tests.factories import make_context


def test_build_application_공통_핸들러_등록(config):
    application = build_application(config)
    assert application.bot_data["config"] is config

    handlers = application.handlers[0]
    assert len(handlers) == 4
    assert len(application.error_handlers) == 1


def test_build_application_help_text_저장(config):
    application = build_application(config, help_text="/price - 시세")
    assert application.bot_data["help_text"] == "/price - 시세"


async def test_post_init_setup_teardown_호출(tmp_path):
    from app.config import Config

    config = Config(
        bot_token="123456:TEST-TOKEN",
        gemini_api_key="test-key",
        db_path=str(tmp_path / "bot.db"),
    )
    calls: list[str] = []

    async def setup(application):
        calls.append("setup")

    async def teardown(application):
        calls.append("teardown")

    application = build_application(config, setup=setup, teardown=teardown)
    await application.post_init(application)
    assert calls == ["setup"]
    assert "db" in application.bot_data

    await application.post_shutdown(application)
    assert calls == ["setup", "teardown"]


def test_build_application_추가_핸들러_등록(config):
    from telegram.ext import CommandHandler

    async def dummy(update, context):  # pragma: no cover — 등록만 확인
        pass

    application = build_application(config, extra_handlers=[CommandHandler("dummy", dummy)])
    assert len(application.handlers[0]) == 5


async def test_on_error_관리자에게_알림(config):
    from dataclasses import replace

    admin_config = replace(config, admin_chat_id=555)
    context = make_context(bot_data={"config": admin_config}, error=ValueError("테스트 오류"))
    await on_error(object(), context)
    context.bot.send_message.assert_awaited_once()
    assert context.bot.send_message.await_args.kwargs["chat_id"] == 555


async def test_on_error_관리자_없으면_알림_안함(config):
    context = make_context(bot_data={"config": config}, error=ValueError("테스트 오류"))
    await on_error(object(), context)
    context.bot.send_message.assert_not_awaited()


async def test_on_error_알림_실패해도_예외_전파_없음(config):
    from dataclasses import replace

    admin_config = replace(config, admin_chat_id=555)
    context = make_context(bot_data={"config": admin_config}, error=ValueError("테스트 오류"))
    context.bot.send_message.side_effect = RuntimeError("전송 실패")
    await on_error(object(), context)  # 예외가 새어 나오면 실패

"""PTB Application 팩토리 — 공통 핸들러/수명주기 등록."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable, Sequence

from telegram import BotCommand
from telegram.ext import (
    Application,
    ApplicationBuilder,
    BaseHandler,
    CommandHandler,
    ContextTypes,
)

from app.config import Config
from app.db import Database
from app.handlers import common

logger = logging.getLogger(__name__)

SetupCallback = Callable[[Application], Awaitable[None]]


def build_application(
    config: Config,
    *,
    migrations: Sequence[str] = (),
    extra_handlers: Sequence[BaseHandler] | None = None,
    help_text: str | None = None,
    commands: Sequence[BotCommand] | None = None,
    setup: SetupCallback | None = None,
    teardown: SetupCallback | None = None,
) -> Application:
    """공통 명령어·DB 수명주기·오류 핸들러가 등록된 Application을 만든다.

    Args:
        config: 환경변수에서 로딩한 설정.
        migrations: 순서대로 적용할 SQL 스크립트 목록 (user_version 기반).
        extra_handlers: 봇별 기능 핸들러. 공통 핸들러 뒤에 등록된다.
        help_text: /help 응답을 봇에 맞게 교체한다.
        commands: 텔레그램 명령어 메뉴에 등록할 목록 (post_init에서 setMyCommands).
        setup: DB 연결 후 실행할 초기화 콜백 (HTTP 클라이언트·서비스 생성 등).
        teardown: 종료 직전 실행할 정리 콜백 (리소스 close 등).
    """

    async def post_init(application: Application) -> None:
        db = Database(config.db_path)
        await db.connect(migrations)
        application.bot_data["db"] = db
        application.bot_data[common.STARTED_AT_KEY] = time.time()
        if commands:
            await application.bot.set_my_commands(list(commands))
        if setup is not None:
            await setup(application)
        logger.info("봇 초기화 완료 (DB: %s)", config.db_path)

    async def post_shutdown(application: Application) -> None:
        if teardown is not None:
            await teardown(application)
        db: Database | None = application.bot_data.get("db")
        if db is not None:
            await db.close()
        logger.info("봇 종료 완료")

    application = (
        ApplicationBuilder()
        .token(config.bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.bot_data["config"] = config
    if help_text:
        application.bot_data["help_text"] = help_text

    application.add_handler(CommandHandler("start", common.cmd_start))
    application.add_handler(CommandHandler("help", common.cmd_help))
    application.add_handler(CommandHandler("status", common.cmd_status))
    application.add_handler(CommandHandler("id", common.cmd_id))
    for handler in extra_handlers or ():
        application.add_handler(handler)

    application.add_error_handler(on_error)
    return application


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("핸들러 오류", exc_info=context.error)

    config: Config | None = context.bot_data.get("config")
    if config is None or config.admin_chat_id is None:
        return
    try:
        await context.bot.send_message(
            chat_id=config.admin_chat_id,
            text=f"오류 발생: {type(context.error).__name__}: {context.error}",
        )
    except Exception:  # noqa: BLE001 — 알림 실패가 봇을 죽이면 안 된다
        logger.warning("관리자 오류 알림 전송 실패", exc_info=True)

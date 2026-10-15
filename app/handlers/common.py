"""모든 봇이 공통으로 쓰는 기본 명령어."""

from __future__ import annotations

import time

from telegram import Update
from telegram.ext import ContextTypes

STARTED_AT_KEY = "started_at"

DEFAULT_HELP = (
    "/start - 인사말\n"
    "/help - 명령어 목록\n"
    "/status - 봇 상태\n"
    "/id - 내 chat id 확인"
)


def format_uptime(seconds: float) -> str:
    seconds = int(seconds)
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)

    parts: list[str] = []
    if days:
        parts.append(f"{days}일")
    if hours or days:
        parts.append(f"{hours}시간")
    parts.append(f"{minutes}분 {secs}초")
    return " ".join(parts)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return
    name = update.effective_user.first_name if update.effective_user else "안녕하세요"
    await update.effective_message.reply_text(
        f"{name}님, 안녕하세요!\n"
        "이 봇은 DashCloud에서 24시간 가동됩니다.\n\n"
        "명령어 목록은 /help 를 참고하세요."
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return
    help_text = context.bot_data.get("help_text") or DEFAULT_HELP
    await update.effective_message.reply_text(help_text)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return
    started_at = float(context.bot_data.get(STARTED_AT_KEY, time.time()))
    db = context.bot_data.get("db")
    db_state = "연결됨" if db is not None else "없음"
    await update.effective_message.reply_text(
        "상태: 정상 가동 중\n"
        f"가동 시간: {format_uptime(time.time() - started_at)}\n"
        f"DB: {db_state}"
    )


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None or update.effective_chat is None:
        return
    await update.effective_message.reply_text(f"chat id: {update.effective_chat.id}")

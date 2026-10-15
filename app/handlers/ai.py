"""AI 비서 명령어와 메시지 핸들러."""

from __future__ import annotations

import io
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from telegram import Message, MessageEntity, Update
from telegram.error import TelegramError
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from app.clients.gemini import GeminiClient, GeminiError, RateLimitError
from app.services.repository import HISTORY_TURNS, Repository
from app.utils.text import chunk_text

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

DAILY_LIMIT = 30  # 유저별 일일 요청 제한 (무료 티어 보호)
DEFAULT_IMAGE_PROMPT = "이 이미지에 무엇이 있는지 한국어로 설명해줘"

AI_HELP = """AI 비서 봇 — 명령어 목록

그냥 메시지를 보내면 AI가 답합니다.
그룹방에서는 봇을 멘션하거나 봇 메시지에 답장할 때만 응답합니다.

/reset — 대화 기억 초기화
/persona 너는 친절한 비서야 — 봇 성격(시스템 프롬프트) 설정
/persona off — 페르소나 해제
/usage — 오늘 사용량 확인 (하루 30회)

사진을 보내면 이미지를 분석합니다.

/status — 봇 상태 · /id — 내 chat id

무료 Gemini API + 대시클라우드 무료 플랜으로 24시간 동작합니다."""


def handlers() -> list[CommandHandler | MessageHandler]:
    return [
        CommandHandler("reset", cmd_reset),
        CommandHandler("persona", cmd_persona),
        CommandHandler("usage", cmd_usage),
        MessageHandler(filters.PHOTO, on_photo),
        MessageHandler(filters.TEXT & ~filters.COMMAND, on_text),
    ]


# ---- 내부 헬퍼 -------------------------------------------------------------


def _repo(context: ContextTypes.DEFAULT_TYPE) -> Repository:
    return context.bot_data["repo"]


def _gemini(context: ContextTypes.DEFAULT_TYPE) -> GeminiClient:
    return context.bot_data["gemini"]


def _today() -> str:
    return datetime.now(KST).strftime("%Y%m%d")


def _mentioned(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """그룹방에서 봇이 호출되었는지 (멘션 또는 봇 메시지에 답장)."""
    message = update.effective_message
    if message is None:
        return False

    reply = message.reply_to_message
    if reply is not None and reply.from_user is not None and reply.from_user.is_bot:
        return True

    username = (context.bot.username or "").lower()
    if not username:
        return False
    text = message.text or message.caption or ""
    for entity in message.entities or []:
        if entity.type == MessageEntity.MENTION:
            mention = text[entity.offset : entity.offset + entity.length]
            if mention.lower() == f"@{username}":
                return True
    return False


def _strip_mention(text: str, username: str | None) -> str:
    if not username:
        return text.strip()
    marker = f"@{username}"
    stripped = text.replace(marker, " ")
    if stripped == text:
        # 대소문자 무시 폴백
        lowered = text.lower()
        index = lowered.find(marker.lower())
        if index >= 0:
            stripped = text[:index] + " " + text[index + len(marker) :]
    return stripped.strip()


async def _reply(context: ContextTypes.DEFAULT_TYPE, message: Message, text: str) -> None:
    try:
        for chunk in chunk_text(text):
            await message.reply_text(chunk)
    except TelegramError:
        logger.warning("응답 전송 실패", exc_info=True)


async def _check_and_consume(
    context: ContextTypes.DEFAULT_TYPE, user_id: int, message: Message
) -> bool:
    """사용량 한도 확인 후 1회 소비. 한도 초과면 안내 후 False."""
    repo = _repo(context)
    used = await repo.get_usage(user_id, _today())
    if used >= DAILY_LIMIT:
        await message.reply_text(
            f"오늘 사용량({DAILY_LIMIT}회)을 모두 썼습니다. 내일 다시 이용해주세요."
        )
        return False
    await repo.increment_usage(user_id, _today())
    return True


def _friendly_error(error: Exception) -> str:
    if isinstance(error, RateLimitError):
        return "지금 무료 사용량이 몰려 답변을 못 만들었어요. 잠시 후 다시 시도해주세요."
    return "AI 응답에 실패했습니다. 잠시 후 다시 시도해주세요."


# ---- 메시지 핸들러 ---------------------------------------------------------


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if message is None or chat is None or user is None or not message.text:
        return
    if chat.type != "private" and not _mentioned(update, context):
        return

    text = _strip_mention(message.text, context.bot.username)
    if not text:
        return

    if not await _check_and_consume(context, user.id, message):
        return

    repo = _repo(context)
    history = await repo.recent_history(user.id, chat.id, HISTORY_TURNS * 2)
    persona = await repo.get_persona(user.id, chat.id)

    try:
        answer = await _gemini(context).generate(history, text, persona)
    except (GeminiError, httpx.HTTPError) as error:
        logger.warning("Gemini 호출 실패", exc_info=True)
        await message.reply_text(_friendly_error(error))
        return

    await repo.add_message(user.id, chat.id, "user", text, datetime.now(KST).isoformat())
    await repo.add_message(user.id, chat.id, "model", answer, datetime.now(KST).isoformat())
    await _reply(context, message, answer)


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if message is None or chat is None or user is None or not message.photo:
        return
    if chat.type != "private" and not _mentioned(update, context):
        return

    if not await _check_and_consume(context, user.id, message):
        return

    prompt = (message.caption or "").strip() or DEFAULT_IMAGE_PROMPT
    prompt = _strip_mention(prompt, context.bot.username) or DEFAULT_IMAGE_PROMPT

    try:
        photo = message.photo[-1]  # 가장 큰 해상도
        file = await context.bot.get_file(photo.file_id)
        buffer = io.BytesIO()
        await file.download_to_memory(buffer)
        answer = await _gemini(context).describe_image(
            buffer.getvalue(), "image/jpeg", prompt
        )
    except (GeminiError, httpx.HTTPError) as error:
        logger.warning("이미지 분석 실패", exc_info=True)
        await message.reply_text(_friendly_error(error))
        return
    except TelegramError:
        logger.warning("이미지 다운로드 실패", exc_info=True)
        await message.reply_text("이미지를 불러오지 못했습니다. 다시 시도해주세요.")
        return

    await _reply(context, message, answer)


# ---- 명령어 ----------------------------------------------------------------


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if (
        update.effective_message is None
        or update.effective_chat is None
        or update.effective_user is None
    ):
        return
    removed = await _repo(context).clear_history(
        update.effective_user.id, update.effective_chat.id
    )
    await update.effective_message.reply_text(
        f"대화 기억을 초기화했습니다. (지운 기록 {removed}건)"
    )


async def cmd_persona(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if (
        update.effective_message is None
        or update.effective_chat is None
        or update.effective_user is None
    ):
        return
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    repo = _repo(context)

    if not context.args:
        persona = await repo.get_persona(user_id, chat_id)
        state = persona if persona else "설정 없음"
        await update.effective_message.reply_text(
            f"현재 페르소나: {state}\n"
            "사용법: /persona 너는 친절한 비서야 또는 /persona off"
        )
        return

    raw = " ".join(context.args)
    if raw.lower() in {"off", "해제", "초기화"}:
        await repo.clear_persona(user_id, chat_id)
        await update.effective_message.reply_text("페르소나를 해제했습니다.")
        return

    await repo.set_persona(user_id, chat_id, raw)
    await update.effective_message.reply_text(f"페르소나 설정: {raw}")


async def cmd_usage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None or update.effective_user is None:
        return
    used = await _repo(context).get_usage(update.effective_user.id, _today())
    await update.effective_message.reply_text(
        f"오늘 사용량: {used}/{DAILY_LIMIT}회 (자정 초기화)"
    )

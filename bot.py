"""gemini-ai-bot 엔트리포인트.

무료 Gemini API로 동작하는 24/7 AI 비서 텔레그램 봇.
대화 기억, 페르소나, 이미지 분석, 그룹방 멘션 응답을 지원합니다.
"""

from __future__ import annotations

import logging

import httpx
from dotenv import load_dotenv
from telegram import BotCommand, Update

from app.bot import build_application
from app.clients.gemini import GeminiClient
from app.config import Config
from app.handlers import ai
from app.services.repository import Repository

MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS conversations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      chat_id INTEGER NOT NULL,
      role TEXT NOT NULL,
      content TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS personas (
      user_id INTEGER NOT NULL,
      chat_id INTEGER NOT NULL,
      prompt TEXT NOT NULL,
      PRIMARY KEY (user_id, chat_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS usage (
      user_id INTEGER NOT NULL,
      day TEXT NOT NULL,
      count INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY (user_id, day)
    );
    """,
]

COMMANDS = [
    BotCommand("reset", "대화 기억 초기화"),
    BotCommand("persona", "봇 성격 설정"),
    BotCommand("usage", "오늘 사용량"),
    BotCommand("start", "시작"),
    BotCommand("help", "명령어 목록"),
    BotCommand("status", "봇 상태"),
    BotCommand("id", "내 chat id"),
]


async def setup(application) -> None:
    config: Config = application.bot_data["config"]
    http = httpx.AsyncClient(timeout=60.0)
    application.bot_data["http"] = http
    application.bot_data["gemini"] = GeminiClient(
        http, config.gemini_api_key, model=config.gemini_model
    )
    application.bot_data["repo"] = Repository(application.bot_data["db"])


async def teardown(application) -> None:
    http: httpx.AsyncClient | None = application.bot_data.get("http")
    if http is not None:
        await http.aclose()


def main() -> None:
    load_dotenv()
    config = Config.from_env()
    logging.basicConfig(
        level=config.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    application = build_application(
        config,
        migrations=MIGRATIONS,
        extra_handlers=ai.handlers(),
        help_text=ai.AI_HELP,
        commands=COMMANDS,
        setup=setup,
        teardown=teardown,
    )
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

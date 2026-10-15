"""PTB Update/Context 테스트 팩토리 (멘션·사진 지원)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from telegram import Bot, Update


def make_bot() -> MagicMock:
    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))
    bot.answer_callback_query = AsyncMock()
    return bot


def make_message_update(
    text: str = "/start",
    *,
    user_id: int = 100,
    chat_id: int = 100,
    chat_type: str = "private",
    first_name: str = "테스터",
    update_id: int = 1,
    entities: list[dict] | None = None,
    reply_to: dict | None = None,
) -> Update:
    message: dict = {
        "message_id": 1,
        "date": int(datetime.now(UTC).timestamp()),
        "chat": {"id": chat_id, "type": chat_type},
        "from": {"id": user_id, "is_bot": False, "first_name": first_name},
        "text": text,
    }
    if entities:
        message["entities"] = entities
    if reply_to:
        message["reply_to_message"] = reply_to
    update = Update.de_json({"update_id": update_id, "message": message}, bot=make_bot())
    assert update is not None
    return update


def make_photo_update(
    caption: str | None = None,
    *,
    user_id: int = 100,
    chat_id: int = 100,
    chat_type: str = "private",
    update_id: int = 3,
) -> Update:
    message: dict = {
        "message_id": 2,
        "date": int(datetime.now(UTC).timestamp()),
        "chat": {"id": chat_id, "type": chat_type},
        "from": {"id": user_id, "is_bot": False, "first_name": "테스터"},
        "photo": [
            {"file_id": "small", "file_unique_id": "s1", "width": 90, "height": 90},
            {"file_id": "large", "file_unique_id": "l1", "width": 1280, "height": 1280},
        ],
    }
    if caption is not None:
        message["caption"] = caption
    update = Update.de_json({"update_id": update_id, "message": message}, bot=make_bot())
    assert update is not None
    return update


def make_context(
    *,
    args: list[str] | None = None,
    bot_data: dict | None = None,
    error: BaseException | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        bot=make_bot(),
        args=args or [],
        bot_data=bot_data or {},
        user_data={},
        chat_data={},
        error=error,
    )


def make_ctx_for(update: Update, **kwargs) -> SimpleNamespace:
    message = update.effective_message
    args = message.text.split()[1:] if message is not None and message.text else []
    return make_context(args=args, **kwargs)

"""SQLite 저장소 (대화 기록·페르소나·사용량)."""

from __future__ import annotations

from app.db import Database

HISTORY_TURNS = 10  # Gemini에 보낼 최근 대화 (user+model 쌍 기준)


class Repository:
    def __init__(self, db: Database) -> None:
        self._db = db

    # ---- 대화 기록 ---------------------------------------------------------

    async def add_message(
        self, user_id: int, chat_id: int, role: str, content: str, created_at: str
    ) -> None:
        await self._db.execute(
            "INSERT INTO conversations (user_id, chat_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, chat_id, role, content, created_at),
        )

    async def recent_history(
        self, user_id: int, chat_id: int, limit: int = HISTORY_TURNS * 2
    ) -> list[tuple[str, str]]:
        rows = await self._db.fetchall(
            "SELECT role, content FROM conversations "
            "WHERE user_id = ? AND chat_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, chat_id, limit),
        )
        return [(str(row["role"]), str(row["content"])) for row in reversed(rows)]

    async def clear_history(self, user_id: int, chat_id: int) -> int:
        return await self._db.execute_affected(
            "DELETE FROM conversations WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id),
        )

    # ---- 페르소나 ---------------------------------------------------------

    async def set_persona(self, user_id: int, chat_id: int, prompt: str) -> None:
        await self._db.execute(
            "INSERT INTO personas (user_id, chat_id, prompt) VALUES (?, ?, ?) "
            "ON CONFLICT (user_id, chat_id) DO UPDATE SET prompt = excluded.prompt",
            (user_id, chat_id, prompt),
        )

    async def get_persona(self, user_id: int, chat_id: int) -> str | None:
        row = await self._db.fetchone(
            "SELECT prompt FROM personas WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id),
        )
        return str(row["prompt"]) if row is not None else None

    async def clear_persona(self, user_id: int, chat_id: int) -> bool:
        affected = await self._db.execute_affected(
            "DELETE FROM personas WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id),
        )
        return affected > 0

    # ---- 사용량 -----------------------------------------------------------

    async def increment_usage(self, user_id: int, day: str) -> int:
        await self._db.execute(
            "INSERT INTO usage (user_id, day, count) VALUES (?, ?, 1) "
            "ON CONFLICT (user_id, day) DO UPDATE SET count = count + 1",
            (user_id, day),
        )
        row = await self._db.fetchone(
            "SELECT count FROM usage WHERE user_id = ? AND day = ?", (user_id, day)
        )
        return int(row["count"]) if row is not None else 0

    async def get_usage(self, user_id: int, day: str) -> int:
        row = await self._db.fetchone(
            "SELECT count FROM usage WHERE user_id = ? AND day = ?", (user_id, day)
        )
        return int(row["count"]) if row is not None else 0

"""aiosqlite 기반 SQLite 헬퍼 (WAL + user_version 마이그레이션)."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)


class Database:
    """봇 상태를 영구 보존하는 SQLite 래퍼.

    - WAL 모드로 읽기/쓰기 동시성 확보
    - ``PRAGMA user_version`` 기반 순차 마이그레이션 (재시작해도 한 번만 적용)
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._conn: aiosqlite.Connection | None = None

    @property
    def connection(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database.connect()를 먼저 호출하세요.")
        return self._conn

    async def connect(self, migrations: Sequence[str] = ()) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._apply_migrations(migrations)
        logger.info("SQLite 연결 완료: %s", self.path)

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def _apply_migrations(self, migrations: Sequence[str]) -> None:
        cursor = await self.connection.execute("PRAGMA user_version")
        row = await cursor.fetchone()
        current = int(row[0]) if row else 0
        for version, script in enumerate(migrations, start=1):
            if version <= current:
                continue
            await self.connection.executescript(script)
            await self.connection.execute(f"PRAGMA user_version={version}")
            await self.connection.commit()
            logger.info("마이그레이션 적용: v%d", version)

    async def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        await self.connection.execute(sql, tuple(params))
        await self.connection.commit()

    async def execute_affected(self, sql: str, params: Iterable[Any] = ()) -> int:
        """실행 후 영향받은 행 수를 반환한다 (INSERT OR IGNORE 중복 판별 등)."""
        cursor = await self.connection.execute(sql, tuple(params))
        await self.connection.commit()
        return int(cursor.rowcount)

    async def executemany(self, sql: str, rows: list[tuple]) -> None:
        await self.connection.executemany(sql, rows)
        await self.connection.commit()

    async def fetchone(self, sql: str, params: Iterable[Any] = ()) -> aiosqlite.Row | None:
        cursor = await self.connection.execute(sql, tuple(params))
        return await cursor.fetchone()

    async def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[aiosqlite.Row]:
        cursor = await self.connection.execute(sql, tuple(params))
        return list(await cursor.fetchall())

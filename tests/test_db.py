"""Database (SQLite + 마이그레이션) 테스트."""

from __future__ import annotations

import pytest

from app.db import Database

MIGRATIONS = [
    "CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, name TEXT NOT NULL);",
    "ALTER TABLE items ADD COLUMN done INTEGER NOT NULL DEFAULT 0;",
]


async def test_연결하면_파일이_생성되고_WAL_모드(tmp_path):
    database = Database(tmp_path / "nested" / "bot.db")
    await database.connect()
    try:
        row = await database.fetchone("PRAGMA journal_mode")
        assert row is not None
        assert row[0] == "wal"
        assert database.path.exists()
    finally:
        await database.close()


async def test_마이그레이션은_한_번만_적용된다(tmp_path):
    path = tmp_path / "bot.db"

    first = Database(path)
    await first.connect(MIGRATIONS)
    await first.execute("INSERT INTO items (name) VALUES (?)", ["첫 번째"])
    await first.close()

    second = Database(path)
    await second.connect(MIGRATIONS)  # 두 번째 적용 시도 — 에러 없이 스킵되어야 함
    try:
        row = await second.fetchone("PRAGMA user_version")
        assert row is not None
        assert int(row[0]) == len(MIGRATIONS)
        rows = await second.fetchall("SELECT name, done FROM items")
        assert len(rows) == 1
        assert rows[0]["name"] == "첫 번째"
        assert rows[0]["done"] == 0
    finally:
        await second.close()


async def test_connect_전_사용하면_에러(tmp_path):
    database = Database(tmp_path / "bot.db")
    with pytest.raises(RuntimeError):
        _ = database.connection


async def test_CRUD_왕복(db):
    await db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)")
    await db.execute("INSERT INTO users (id, name) VALUES (?, ?)", [1, "가나다"])

    row = await db.fetchone("SELECT name FROM users WHERE id = ?", [1])
    assert row is not None
    assert row["name"] == "가나다"

    await db.execute("UPDATE users SET name = ? WHERE id = ?", ["라마바", 1])
    rows = await db.fetchall("SELECT name FROM users")
    assert [r["name"] for r in rows] == ["라마바"]

    await db.execute("DELETE FROM users WHERE id = ?", [1])
    assert await db.fetchone("SELECT name FROM users") is None

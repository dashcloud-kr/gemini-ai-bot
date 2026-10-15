"""Repository (대화·페르소나·사용량) 테스트."""

from __future__ import annotations


async def test_대화_기록과_최근_조회(repo):
    await repo.add_message(1, 100, "user", "안녕", "t1")
    await repo.add_message(1, 100, "model", "안녕하세요", "t2")
    await repo.add_message(1, 100, "user", "뭐해", "t3")

    history = await repo.recent_history(1, 100)
    assert history == [("user", "안녕"), ("model", "안녕하세요"), ("user", "뭐해")]

    limited = await repo.recent_history(1, 100, limit=2)
    assert limited == [("model", "안녕하세요"), ("user", "뭐해")]


async def test_대화는_채팅별_분리(repo):
    await repo.add_message(1, 100, "user", "A", "t")
    await repo.add_message(1, 200, "user", "B", "t")
    assert await repo.recent_history(1, 100) == [("user", "A")]
    assert await repo.recent_history(1, 200) == [("user", "B")]


async def test_대화_초기화(repo):
    await repo.add_message(1, 100, "user", "A", "t")
    await repo.add_message(1, 100, "model", "B", "t")
    assert await repo.clear_history(1, 100) == 2
    assert await repo.recent_history(1, 100) == []


async def test_페르소나(repo):
    assert await repo.get_persona(1, 100) is None

    await repo.set_persona(1, 100, "너는 비서야")
    assert await repo.get_persona(1, 100) == "너는 비서야"

    await repo.set_persona(1, 100, "너는 코치야")  # 덮어쓰기
    assert await repo.get_persona(1, 100) == "너는 코치야"

    assert await repo.clear_persona(1, 100) is True
    assert await repo.clear_persona(1, 100) is False
    assert await repo.get_persona(1, 100) is None


async def test_사용량(repo):
    assert await repo.get_usage(1, "20261015") == 0
    assert await repo.increment_usage(1, "20261015") == 1
    assert await repo.increment_usage(1, "20261015") == 2
    assert await repo.get_usage(1, "20261015") == 2

    # 다른 날/다른 유저는 별도
    assert await repo.get_usage(1, "20261016") == 0
    assert await repo.get_usage(2, "20261015") == 0


async def test_마이그레이션_재적용_안전(tmp_path):
    from app.db import Database
    from app.services.repository import Repository
    from bot import MIGRATIONS

    path = tmp_path / "again.db"
    first = Database(path)
    await first.connect(MIGRATIONS)
    await Repository(first).add_message(1, 100, "user", "A", "t")
    await first.close()

    second = Database(path)
    await second.connect(MIGRATIONS)
    try:
        assert await Repository(second).recent_history(1, 100) == [("user", "A")]
    finally:
        await second.close()

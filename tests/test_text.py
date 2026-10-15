"""chunk_text 분할 테스트."""

from __future__ import annotations

import pytest

from app.utils.text import chunk_text


def test_짧은_텍스트는_그대로():
    assert chunk_text("안녕하세요", limit=100) == ["안녕하세요"]


def test_빈_문자열은_빈_리스트():
    assert chunk_text("", limit=100) == []


def test_제한과_정확히_같으면_한_덩어리():
    text = "a" * 100
    assert chunk_text(text, limit=100) == [text]


def test_줄바꿈_경계로_분할():
    lines = [f"{i}번째 줄 " + "x" * 20 for i in range(10)]
    text = "\n".join(lines)
    chunks = chunk_text(text, limit=100)
    assert len(chunks) > 1
    assert all(len(c) <= 100 for c in chunks)
    assert "\n".join(chunks) == text


def test_긴_한_줄은_강제로_자른다():
    text = "y" * 5000
    chunks = chunk_text(text, limit=4096)
    assert [len(c) for c in chunks] == [4096, 904]
    assert "".join(chunks) == text


def test_모든_청크는_제한_이하():
    text = ("가" * 3000 + "\n") * 5
    chunks = chunk_text(text, limit=4096)
    assert all(len(c) <= 4096 for c in chunks)


def test_limit이_0이하면_에러():
    with pytest.raises(ValueError):
        chunk_text("abc", limit=0)

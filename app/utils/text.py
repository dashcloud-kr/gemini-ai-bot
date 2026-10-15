"""메시지 텍스트 유틸."""

from __future__ import annotations

TELEGRAM_MESSAGE_LIMIT = 4096


def chunk_text(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """긴 텍스트를 텔레그램 길이 제한에 맞게 분할한다.

    줄바꿈 경계를 우선 사용하고, 한 줄이 제한보다 길면 강제로 자른다.
    """
    if limit <= 0:
        raise ValueError("limit은 1 이상이어야 합니다.")
    if len(text) <= limit:
        return [text] if text else []

    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        window = remaining[:limit]
        split_at = window.rfind("\n")
        if split_at <= 0:
            split_at = limit
        chunks.append(remaining[:split_at].rstrip("\n"))
        remaining = remaining[split_at:].lstrip("\n")
    if remaining:
        chunks.append(remaining)
    return chunks

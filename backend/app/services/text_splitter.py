"""Character-window text splitter with overlap.

Naive but predictable: walks `chunk_chars` characters at a time, stepping by
`chunk_chars - chunk_overlap`. Good enough for MVP; LangChain's
RecursiveCharacterTextSplitter would be a drop-in upgrade later if quality
becomes an issue.
"""
from __future__ import annotations


def split_text(text: str, *, chunk_chars: int, chunk_overlap: int) -> list[str]:
    if chunk_overlap >= chunk_chars:
        raise ValueError("chunk_overlap must be smaller than chunk_chars")
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_chars:
        return [text]
    step = chunk_chars - chunk_overlap
    out: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_chars, len(text))
        chunk = text[start:end].strip()
        if chunk:
            out.append(chunk)
        if end == len(text):
            break
        start += step
    return out

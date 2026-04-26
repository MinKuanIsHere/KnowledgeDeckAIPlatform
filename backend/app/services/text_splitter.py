"""Recursive sentence-aware text splitter.

Wraps LangChain's RecursiveCharacterTextSplitter so chunk boundaries land
on natural breaks (paragraph -> newline -> sentence -> word -> char) rather
than mid-sentence. Same public API as the previous naive splitter so
callers don't change.

Why character counts (not tokens): bge-m3 tokenizer isn't loaded in the
backend runtime, and char-based windows correlate well enough with token
counts for our embedding model. Default chunk_chars=1200 keeps each chunk
well under bge-m3's 8K context.
"""
from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter


def split_text(text: str, *, chunk_chars: int, chunk_overlap: int) -> list[str]:
    if chunk_overlap >= chunk_chars:
        raise ValueError("chunk_overlap must be smaller than chunk_chars")
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_chars:
        return [text]
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_chars,
        chunk_overlap=chunk_overlap,
        # Order matters: highest-priority natural break first. Falls through
        # until a separator can fit the chunk under chunk_size.
        separators=["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""],
        length_function=len,
        is_separator_regex=False,
    )
    return [s for s in (chunk.strip() for chunk in splitter.split_text(text)) if s]

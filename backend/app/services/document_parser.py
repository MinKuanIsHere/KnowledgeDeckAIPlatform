"""Parse uploaded files into a list of (text, page_number) segments.

TXT/CS produce one segment with page_number=None.
PDF produces one segment per page with page_number set.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

from pypdf import PdfReader


@dataclass
class ParsedSegment:
    text: str
    page_number: int | None  # 1-based; None for non-paginated formats


def parse(extension: str, data: bytes) -> list[ParsedSegment]:
    if extension in ("txt", "cs"):
        return [ParsedSegment(text=data.decode("utf-8", errors="replace"), page_number=None)]
    if extension == "pdf":
        reader = PdfReader(io.BytesIO(data))
        out: list[ParsedSegment] = []
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                out.append(ParsedSegment(text=text, page_number=i))
        return out
    raise ValueError(f"unsupported extension: {extension}")

"""Read-only LLM metadata endpoint.

Exposes the currently configured chat model so the UI can show a label
("Model: Gemma 4 E4B") in the chat / slide-maker headers without
hardcoding the name on the frontend. Selection / multi-model support is
deliberately not part of this endpoint — see note-todo.md.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.shared.api.deps import get_current_user
from app.core.config import get_settings
from app.db.models import User

router = APIRouter(prefix="/llm", tags=["llm"])


class LlmInfo(BaseModel):
    label: str
    model_id: str


@router.get("/info", response_model=LlmInfo)
def llm_info(_user: User = Depends(get_current_user)) -> LlmInfo:
    s = get_settings()
    return LlmInfo(label=s.llm_model_label, model_id=s.llm_model)

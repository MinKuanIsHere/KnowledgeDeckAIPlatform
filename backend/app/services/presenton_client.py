"""Thin async wrapper over Presenton's REST API.

We use Presenton purely as a rendering service: we hand it the per-slide
markdown we already produced (so its outline LLM is bypassed) and it returns
a path to the rendered PPTX inside its container. The path resolves on a
shared volume that backend mounts read-only.
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class PresentonError(RuntimeError):
    pass


class PresentonClient:
    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        shared_data_root: str,
        timeout: float = 180.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._auth_header = f"Basic {token}"
        self._shared_data_root = Path(shared_data_root)
        self._timeout = timeout

    async def generate(
        self,
        *,
        slides_markdown: list[str],
        n_slides: int,
        language: str = "English",
        template: str = "general",
        export_as: str = "pptx",
    ) -> dict[str, Any]:
        """Sync /generate. Blocks until the PPTX is rendered.

        We send the user-confirmed outline as a single `content` blob rather
        than the per-slide `slides_markdown` array because the slides_markdown
        code path in presenton:latest crashes inside an internal helper
        (`PresentationLayoutModel.to_string()` API mismatch). The downside is
        that Presenton runs its own outline pass on top of our content, so the
        final deck may diverge slightly from the user-confirmed outline.
        Presenton's outline LLM is pointed at our vLLM via CUSTOM_LLM_URL, so
        the model is unchanged — only the prompt structure differs.
        """
        content = "\n\n".join(slides_markdown)
        payload = {
            "content": content,
            "n_slides": n_slides,
            "language": language,
            "template": template,
            "export_as": export_as,
        }
        url = f"{self._base_url}/api/v1/ppt/presentation/generate"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"Authorization": self._auth_header},
            )
            if response.status_code >= 400:
                raise PresentonError(
                    f"Presenton {response.status_code}: {response.text[:300]}"
                )
            return response.json()

    def read_artifact(self, container_path: str) -> bytes:
        """Read a Presenton-generated file from the shared volume.

        Presenton returns paths like `/app_data/presentations/<id>.pptx`.
        Backend mounts the same volume at `presenton_data_root` (default
        `/presenton_data`), so we strip the `/app_data` prefix and resolve
        from there.
        """
        if not container_path.startswith("/app_data/"):
            raise PresentonError(
                f"unexpected presenton path (not under /app_data): {container_path}"
            )
        relative = container_path[len("/app_data/"):]
        resolved = (self._shared_data_root / relative).resolve()
        # Sanity check: the resolved path must stay under the shared root.
        if not str(resolved).startswith(str(self._shared_data_root)):
            raise PresentonError(f"refusing to read outside shared root: {resolved}")
        if not resolved.exists():
            raise PresentonError(f"presenton artifact not found: {resolved}")
        return resolved.read_bytes()


_client: PresentonClient | None = None


def get_presenton_client() -> PresentonClient:
    global _client
    if _client is None:
        s = get_settings()
        _client = PresentonClient(
            base_url=s.presenton_url,
            username=s.presenton_username,
            password=s.presenton_password,
            shared_data_root=s.presenton_data_root,
        )
    return _client

from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings
from app.main import create_app


def _middleware_classes(app):
    return [m.cls for m in app.user_middleware]


def test_cors_middleware_skipped_when_origins_unset() -> None:
    """Default settings have empty cors_origins → no CORS middleware attached."""
    app = create_app()
    assert CORSMiddleware not in _middleware_classes(app)


def test_cors_middleware_attached_when_origins_configured(monkeypatch) -> None:
    """When cors_origins is set, the middleware is added with those origins."""
    monkeypatch.setattr(
        "app.main.get_settings",
        lambda: Settings(cors_origins="http://example.test:3000,http://other.test:3000"),
    )
    app = create_app()
    assert CORSMiddleware in _middleware_classes(app)


def test_cors_origins_list_parses_csv() -> None:
    """The Settings helper splits, trims, and drops empties."""
    s = Settings(cors_origins="http://a:3000, http://b:3000 ,,")
    assert s.cors_origins_list == ["http://a:3000", "http://b:3000"]

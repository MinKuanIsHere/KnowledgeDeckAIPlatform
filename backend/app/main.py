from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.startup import lifespan


def create_app() -> FastAPI:
    app = FastAPI(title="KnowledgeDeck API", version="0.1.0", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(auth_router)
    return app


app = create_app()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.core.config import get_settings
from app.startup import lifespan


def create_app() -> FastAPI:
    app = FastAPI(title="KnowledgeDeck API", version="0.1.0", lifespan=lifespan)

    origins = get_settings().cors_origins_list
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["Authorization", "Content-Type"],
        )

    app.include_router(health_router)
    app.include_router(auth_router)
    return app


app = create_app()

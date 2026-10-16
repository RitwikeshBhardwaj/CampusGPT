from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import init_db
from app.health import router as health_router
from app.log_config import LoggingMiddleware, logger
from app.routes_auth import router as auth_router
from app.routes_chat import router as chat_router
from app.routes_conversations import router as conversations_router
from app.routes_documents import router as documents_router
from app.routes_users import router as users_router


def create_app() -> FastAPI:
    settings.ensure_dirs()
    init_db(settings.db_path)

    app = FastAPI(title="CampusGPT")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(LoggingMiddleware)

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(conversations_router)
    app.include_router(documents_router)
    app.include_router(chat_router)

    return app


app = create_app()
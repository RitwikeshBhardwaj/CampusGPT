from fastapi import FastAPI

from app.config import settings
from app.db import init_db
from app.health import router as health_router


def create_app() -> FastAPI:
    settings.ensure_dirs()
    init_db(settings.db_path)
    app = FastAPI(title="CampusGPT")
    app.include_router(health_router)
    return app


app = create_app()

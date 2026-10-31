import logging
from app.auth import hash_password
from app.config import settings
from app.db import create_user, get_user_by_username, init_db

logger = logging.getLogger(__name__)

def bootstrap_admin():
    """Seed the first-run admin account from environment variables."""
    if not settings.admin_user or not settings.admin_pass:
        logger.info("Admin seeding skipped: credentials not provided in environment variables.")
        return

    init_db(settings.db_path)

    if get_user_by_username(settings.db_path, settings.admin_user):
        logger.info(f"Admin user '{settings.admin_user}' already exists.")
        return

    logger.info(f"Seeding admin user: {settings.admin_user}")
    create_user(
        settings.db_path,
        settings.admin_user,
        hash_password(settings.admin_pass),
        "admin"
    )
    logger.info("Admin user created successfully.")

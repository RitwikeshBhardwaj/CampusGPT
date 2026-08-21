"""Password hashing and session-cookie management.

Passwords are hashed with bcrypt (via the ``bcrypt`` library directly — passlib
1.7 is incompatible with bcrypt 5.x, so we use bcrypt natively). Sessions are
signed tokens in an ``httpOnly`` cookie named ``campusgpt_session``.
"""

import json
from typing import Callable

import bcrypt
from fastapi import Depends, HTTPException, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings
from app.db import get_user_by_id


SESSION_COOKIE = "campusgpt_session"
SESSION_MAX_AGE_SECONDS = 7 * 24 * 60 * 60  # 7 days


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the plain password (UTF-8, cost 12)."""
    hashed = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if ``plain`` matches the stored ``hashed`` password."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt="campusgpt-session")


def issue_session(response: Response, user_id: int) -> None:
    """Set a signed session cookie for ``user_id``."""
    payload = json.dumps({"uid": user_id})
    token = _serializer().dumps(payload)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,  # local-only; flip to True behind TLS in production
        path="/",
    )


def read_session(request: Request) -> int | None:
    """Return the authenticated ``user_id`` from the cookie, or None."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        payload = _serializer().loads(token, max_age=SESSION_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    try:
        return int(json.loads(payload).get("uid"))
    except (ValueError, TypeError):
        return None


def clear_session(response: Response) -> None:
    """Delete the session cookie."""
    response.delete_cookie(key=SESSION_COOKIE, path="/")


# --- FastAPI dependencies --------------------------------------------------

def get_current_user(request: Request) -> dict | None:
    """Resolve the current user from the session cookie, or None."""
    uid = read_session(request)
    if uid is None:
        return None
    return get_user_by_id(settings.db_path, uid)


def require_user(request: Request) -> dict:
    """Dependency: require an authenticated user (401 if not logged in)."""
    user = get_current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


def require_role(role: str) -> Callable:
    """Return a dependency that requires the authenticated user to have ``role``."""
    def _dep(request: Request) -> dict:
        user = require_user(request)
        if user["role"] != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Admin role required",
            )
        return user
    return _dep

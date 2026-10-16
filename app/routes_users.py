"""Admin user-management routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import require_role
from app.db import create_user, delete_user, get_user_by_id, list_users

router = APIRouter(prefix="/api/admin", tags=["admin"])


class UserCreate(BaseModel):
    username: str
    password: str
    role: str


class UserResponse(BaseModel):
    id: int
    username: str
    role: str


def _to_user_response(user: dict) -> UserResponse:
    return UserResponse(id=user["id"], username=user["username"], role=user["role"])


@router.get("/users", response_model=list[UserResponse])
def list_users_route(admin: dict = Depends(require_role("admin"))):
    """List all users. Admin only."""
    from app.config import settings
    return [_to_user_response(u) for u in list_users(settings.db_path)]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user_route(body: UserCreate, admin: dict = Depends(require_role("admin"))):
    """Create a new user. Admin only."""
    from app.auth import hash_password
    from app.config import settings
    from app.db import get_user_by_username, init_db

    init_db(settings.db_path)
    if get_user_by_username(settings.db_path, body.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )
    if body.role not in ("student", "admin"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be 'student' or 'admin'",
        )
    uid = create_user(settings.db_path, body.username, hash_password(body.password), body.role)
    user = get_user_by_id(settings.db_path, uid)
    return _to_user_response(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_route(user_id: int, admin: dict = Depends(require_role("admin"))):
    """Delete a user. Admin only; cannot delete self."""
    from app.config import settings
    from app.db import init_db

    init_db(settings.db_path)
    if user_id == admin["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete yourself",
        )
    target = get_user_by_id(settings.db_path, user_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    delete_user(settings.db_path, user_id)
    return None
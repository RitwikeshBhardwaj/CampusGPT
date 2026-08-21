"""Authentication routes: login, logout, me."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from app.auth import (
    clear_session,
    get_current_user,
    issue_session,
    read_session,
    verify_password,
)
from app.config import settings
from app.db import get_user_by_username, init_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    role: str


def _to_user_response(user: dict) -> UserResponse:
    return UserResponse(id=user["id"], username=user["username"], role=user["role"])


@router.post("/login", response_model=UserResponse)
def login(body: LoginRequest, response: Response):
    if not body.username or not body.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password are required",
        )
    init_db(settings.db_path)
    user = get_user_by_username(settings.db_path, body.username)
    if user is None or not verify_password(body.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    issue_session(response, user["id"])
    return _to_user_response(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    clear_session(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserResponse)
def me(user: dict = Depends(get_current_user)):
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return _to_user_response(user)
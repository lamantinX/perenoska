from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_auth_service, get_current_user
from app.schemas import AuthResponse, UserCreate, UserLogin, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
def register(payload: UserCreate, auth_service=Depends(get_auth_service)) -> AuthResponse:
    return auth_service.register(payload)


@router.post("/login", response_model=AuthResponse)
def login(payload: UserLogin, auth_service=Depends(get_auth_service)) -> AuthResponse:
    return auth_service.login(payload)


@router.get("/me", response_model=UserResponse)
def me(user=Depends(get_current_user)) -> UserResponse:
    return UserResponse(id=user["id"], email=user["email"], created_at=user["created_at"])


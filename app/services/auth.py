from __future__ import annotations

from datetime import UTC, datetime, timedelta
from sqlite3 import IntegrityError

from fastapi import HTTPException, status

from app.db import Database
from app.schemas import AuthResponse, UserCreate, UserLogin, UserResponse
from app.security import PasswordManager, generate_session_token


class AuthService:
    def __init__(self, database: Database, password_manager: PasswordManager, session_ttl_hours: int) -> None:
        self.database = database
        self.password_manager = password_manager
        self.session_ttl_hours = session_ttl_hours

    def register(self, payload: UserCreate) -> AuthResponse:
        timestamp = datetime.now(UTC).isoformat()
        try:
            user = self.database.create_user(
                email=payload.email.lower().strip(),
                password_hash=self.password_manager.hash_password(payload.password),
                created_at=timestamp,
            )
        except IntegrityError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Пользователь с таким email уже существует.",
            ) from error
        return self._issue_auth_response(user)

    def login(self, payload: UserLogin) -> AuthResponse:
        user = self.database.get_user_by_email(payload.email.lower().strip())
        if user is None or not self.password_manager.verify_password(payload.password, user["password_hash"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный email или пароль.")
        return self._issue_auth_response(user)

    def get_current_user(self, token: str) -> dict:
        session = self.database.get_session(token)
        if session is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Сессия не найдена.")
        expires_at = datetime.fromisoformat(session["expires_at"])
        if expires_at <= datetime.now(UTC):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Сессия истекла.")
        user = self.database.get_user_by_id(session["user_id"])
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден.")
        return user

    def _issue_auth_response(self, user: dict) -> AuthResponse:
        now = datetime.now(UTC)
        token = generate_session_token()
        self.database.create_session(
            token=token,
            user_id=int(user["id"]),
            expires_at=(now + timedelta(hours=self.session_ttl_hours)).isoformat(),
            created_at=now.isoformat(),
        )
        return AuthResponse(
            access_token=token,
            user=UserResponse(id=int(user["id"]), email=user["email"], created_at=user["created_at"]),
        )


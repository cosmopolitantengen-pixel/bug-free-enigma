from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from collections.abc import Callable

from app.auth.passwords import hash_password, verify_password
from app.core.models import User
from app.services.serializers import to_plain


class AuthError(ValueError):
    pass


DEFAULT_SESSION_TTL_SECONDS = 8 * 60 * 60


@dataclass(frozen=True)
class SessionRecord:
    user_id: str
    expires_at: datetime


@dataclass
class AuthService:
    users: dict[str, User] = field(default_factory=dict)
    sessions: dict[str, SessionRecord] = field(default_factory=dict)
    session_ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS
    clock: Callable[[], datetime] = field(default_factory=lambda: _utc_now, repr=False)

    @classmethod
    def from_env(cls, users: dict[str, User] | None = None) -> "AuthService":
        return cls(users=users or {}, session_ttl_seconds=_session_ttl_from_env())

    def __post_init__(self) -> None:
        if self.session_ttl_seconds <= 0:
            raise AuthError("session TTL must be greater than zero seconds")

    def register(self, email: str, password: str) -> dict:
        normalized_email = email.strip().lower()
        if not normalized_email:
            raise AuthError("email is required")
        if normalized_email in self.users:
            raise AuthError("user already exists")
        user = User(email=normalized_email, password_hash=hash_password(password))
        self.users[normalized_email] = user
        return self.public_user(user)

    def login(self, email: str, password: str) -> dict:
        normalized_email = email.strip().lower()
        user = self.users.get(normalized_email)
        if user is None or not user.enabled or not verify_password(password, user.password_hash):
            raise AuthError("invalid email or password")
        self._prune_expired_sessions()
        token = f"local-dev-token:{secrets.token_urlsafe(32)}"
        expires_at = self._now() + timedelta(seconds=self.session_ttl_seconds)
        self.sessions[token] = SessionRecord(user_id=user.user_id, expires_at=expires_at)
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_at": expires_at.isoformat(),
            "expires_in_seconds": self.session_ttl_seconds,
            "user": self.public_user(user),
        }

    def logout(self, token: str | None = None) -> dict:
        if token:
            self.sessions.pop(token, None)
        return {"status": "ok"}

    def authenticate_session_token(self, token: str) -> User | None:
        session = self.sessions.get(token)
        if session is None:
            return None
        if session.expires_at <= self._now():
            self.sessions.pop(token, None)
            return None
        for user in self.users.values():
            if user.user_id == session.user_id and user.enabled:
                return user
        return None

    def has_users(self) -> bool:
        return bool(self.users)

    def public_user(self, user: User) -> dict:
        payload = to_plain(user)
        payload.pop("password_hash", None)
        return payload

    def list_users(self) -> list[User]:
        return list(self.users.values())

    def _prune_expired_sessions(self) -> None:
        now = self._now()
        expired = [token for token, session in self.sessions.items() if session.expires_at <= now]
        for token in expired:
            self.sessions.pop(token, None)

    def _now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _session_ttl_from_env() -> int:
    raw = (os.environ.get("AI_COMPANY_OS_SESSION_TTL_SECONDS") or "").strip()
    if not raw:
        return DEFAULT_SESSION_TTL_SECONDS
    try:
        ttl = int(raw)
    except ValueError as exc:
        raise AuthError("AI_COMPANY_OS_SESSION_TTL_SECONDS must be an integer") from exc
    if ttl <= 0:
        raise AuthError("AI_COMPANY_OS_SESSION_TTL_SECONDS must be greater than zero")
    return ttl

from __future__ import annotations

import secrets
from dataclasses import dataclass, field

from app.auth.passwords import hash_password, verify_password
from app.core.models import User
from app.services.serializers import to_plain


class AuthError(ValueError):
    pass


@dataclass
class AuthService:
    users: dict[str, User] = field(default_factory=dict)
    sessions: dict[str, str] = field(default_factory=dict)

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
        token = f"local-dev-token:{secrets.token_urlsafe(32)}"
        self.sessions[token] = user.user_id
        return {"access_token": token, "token_type": "bearer", "user": self.public_user(user)}

    def logout(self, token: str | None = None) -> dict:
        if token:
            self.sessions.pop(token, None)
        return {"status": "ok"}

    def public_user(self, user: User) -> dict:
        payload = to_plain(user)
        payload.pop("password_hash", None)
        return payload

    def list_users(self) -> list[User]:
        return list(self.users.values())

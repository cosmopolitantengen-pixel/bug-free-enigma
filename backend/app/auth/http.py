from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from collections.abc import Callable, Awaitable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.company import CompanyApplicationService


class AuthConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class HttpAuthSettings:
    required: bool = False
    api_token: str | None = None
    api_token_sha256: str | None = None

    @classmethod
    def from_env(cls) -> "HttpAuthSettings":
        return cls(
            required=_truthy(os.environ.get("AI_COMPANY_OS_AUTH_REQUIRED")),
            api_token=_blank_to_none(os.environ.get("AI_COMPANY_OS_API_TOKEN")),
            api_token_sha256=_normalize_sha256(os.environ.get("AI_COMPANY_OS_API_TOKEN_SHA256")),
        )

    @property
    def has_static_api_token(self) -> bool:
        return bool(self.api_token or self.api_token_sha256)


class HttpAuthMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        service: CompanyApplicationService,
        settings: HttpAuthSettings,
    ) -> None:
        super().__init__(app)
        self.service = service
        self.settings = settings

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not self.settings.required or request.method == "OPTIONS" or _is_public_path(request.url.path):
            return await call_next(request)

        token = _bearer_token(request.headers.get("authorization"))
        if token and self._valid_token(token):
            return await call_next(request)

        return Response(
            content='{"detail":"authentication required"}',
            media_type="application/json",
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )

    def _valid_token(self, token: str) -> bool:
        if self.service.auth.authenticate_session_token(token) is not None:
            return True
        if self.settings.api_token and hmac.compare_digest(token, self.settings.api_token):
            return True
        if self.settings.api_token_sha256:
            digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
            return hmac.compare_digest(digest, self.settings.api_token_sha256)
        return False


def validate_http_auth_configuration(
    service: CompanyApplicationService,
    settings: HttpAuthSettings,
) -> None:
    if not settings.required:
        return
    if settings.has_static_api_token or service.auth.has_users():
        return
    raise AuthConfigurationError(
        "AI_COMPANY_OS_AUTH_REQUIRED requires AI_COMPANY_OS_API_TOKEN, "
        "AI_COMPANY_OS_API_TOKEN_SHA256, or at least one persisted user"
    )


def _is_public_path(path: str) -> bool:
    return path in {"/health", "/auth/login"}


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value:
        return None
    return value.strip()


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _blank_to_none(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _normalize_sha256(value: str | None) -> str | None:
    value = _blank_to_none(value)
    if value is None:
        return None
    normalized = value.lower()
    if len(normalized) != 64 or any(character not in "0123456789abcdef" for character in normalized):
        raise AuthConfigurationError("AI_COMPANY_OS_API_TOKEN_SHA256 must be a 64-character hex SHA-256 digest")
    return normalized

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import cast
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from pydantic import BaseModel

from .config import get_settings
from .errors import AppError

settings = get_settings()
password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenPayload(BaseModel):
    sub: UUID
    email: str
    role: str
    type: TokenType
    sid: UUID
    exp: datetime
    iat: datetime


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_token(
    *,
    user_id: UUID,
    email: str,
    role: str,
    token_type: TokenType,
    session_id: UUID,
) -> str:
    now = datetime.now(UTC)
    ttl = (
        timedelta(minutes=settings.access_token_ttl_minutes)
        if token_type == TokenType.ACCESS
        else timedelta(days=settings.refresh_token_ttl_days)
    )
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "type": token_type.value,
        "sid": str(session_id),
        "iat": now,
        "exp": now + ttl,
    }
    return cast(str, jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm))


def decode_token(token: str, expected_type: TokenType) -> TokenPayload:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        parsed = TokenPayload.model_validate(payload)
    except jwt.ExpiredSignatureError as exc:
        raise AppError(401, "登录已过期", "请重新登录。", "token_expired") from exc
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise AppError(401, "身份凭证无效", "无法验证当前身份凭证。", "invalid_token") from exc
    if parsed.type != expected_type:
        raise AppError(401, "身份凭证类型错误", "当前凭证不能用于此操作。", "wrong_token_type")
    return parsed

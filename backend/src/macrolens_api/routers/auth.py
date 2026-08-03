from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Cookie, Request, Response
from sqlalchemy import func, or_, select

from ..config import get_settings
from ..dependencies import CurrentUser, SessionDep
from ..errors import AppError
from ..models import RefreshSession, User, Workspace
from ..schemas import AuthResponse, LoginRequest, RegisterRequest, UserPublic
from ..security import (
    TokenType,
    create_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Auth"])
settings = get_settings()


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()[:64]
    return request.client.host[:64] if request.client else None


def _set_auth_cookies(response: Response, user: User, session_id: UUID) -> tuple[str, str]:
    access = create_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        token_type=TokenType.ACCESS,
        session_id=session_id,
    )
    refresh = create_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        token_type=TokenType.REFRESH,
        session_id=session_id,
    )
    common = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "path": "/",
        "domain": settings.cookie_domain,
    }
    response.set_cookie(
        "macrolens_access",
        access,
        max_age=settings.access_token_ttl_minutes * 60,
        **common,
    )
    response.set_cookie(
        "macrolens_refresh",
        refresh,
        max_age=settings.refresh_token_ttl_days * 86400,
        **common,
    )
    return access, refresh


async def _revoke_refresh_family(
    session: SessionDep,
    *,
    root_session_id: UUID,
    revoked_at: datetime,
) -> int:
    """Revoke a rotated refresh-token family after logout or replay detection."""
    frontier = {root_session_id}
    seen: set[UUID] = set()
    revoked = 0
    while frontier:
        rows = list(
            (
                await session.scalars(
                    select(RefreshSession).where(
                        or_(
                            RefreshSession.id.in_(frontier),
                            RefreshSession.rotated_from_id.in_(frontier),
                        )
                    )
                )
            ).all()
        )
        next_frontier: set[UUID] = set()
        for row in rows:
            if row.id not in seen:
                next_frontier.add(row.id)
            if row.revoked_at is None:
                row.revoked_at = revoked_at
                revoked += 1
        seen.update(frontier)
        frontier = next_frontier - seen
    return revoked


async def _create_refresh_session(
    session: SessionDep,
    *,
    request: Request,
    response: Response,
    user: User,
    rotated_from_id: UUID | None = None,
) -> RefreshSession:
    session_id = uuid4()
    _access, refresh = _set_auth_cookies(response, user, session_id)
    auth_session = RefreshSession(
        id=session_id,
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days),
        rotated_from_id=rotated_from_id,
        user_agent=request.headers.get("user-agent", "")[:1000] or None,
        ip_address=_client_ip(request),
    )
    session.add(auth_session)
    return auth_session


@router.get("/config")
async def auth_config() -> dict[str, bool]:
    return {"allow_public_registration": settings.allow_public_registration}


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    session: SessionDep,
) -> AuthResponse:
    if not settings.allow_public_registration:
        raise AppError(403, "暂未开放注册", "请联系管理员创建账号。", "registration_disabled")
    email = payload.email.lower().strip()
    if await session.scalar(select(func.count(User.id)).where(User.email == email)):
        raise AppError(409, "邮箱已注册", "请直接登录或使用其他邮箱。", "email_exists")
    user = User(
        email=email,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        role="researcher",
    )
    session.add(user)
    await session.flush()
    session.add(Workspace(name=f"{user.display_name}的工作区", owner_user_id=user.id))
    await _create_refresh_session(session, request=request, response=response, user=user)
    await session.commit()
    await session.refresh(user)
    return AuthResponse(
        user=UserPublic.model_validate(user),
        access_expires_in_seconds=settings.access_token_ttl_minutes * 60,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
) -> AuthResponse:
    user = await session.scalar(select(User).where(User.email == payload.email.lower().strip()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise AppError(401, "登录失败", "邮箱或密码不正确。", "invalid_credentials")
    if not user.active:
        raise AppError(403, "账号已停用", "请联系管理员。", "inactive_user")
    user.last_login_at = datetime.now(UTC)
    await _create_refresh_session(session, request=request, response=response, user=user)
    await session.commit()
    return AuthResponse(
        user=UserPublic.model_validate(user),
        access_expires_in_seconds=settings.access_token_ttl_minutes * 60,
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    request: Request,
    response: Response,
    session: SessionDep,
    macrolens_refresh: Annotated[str | None, Cookie()] = None,
) -> AuthResponse:
    if not macrolens_refresh:
        raise AppError(401, "刷新凭证缺失", "请重新登录。", "refresh_required")
    token = decode_token(macrolens_refresh, TokenType.REFRESH)
    auth_session = await session.scalar(
        select(RefreshSession).where(RefreshSession.id == token.sid).with_for_update()
    )
    now = datetime.now(UTC)
    invalid = (
        auth_session is None
        or auth_session.user_id != token.sub
        or auth_session.revoked_at is not None
        or auth_session.expires_at <= now
        or auth_session.refresh_token_hash != hash_refresh_token(macrolens_refresh)
    )
    if invalid:
        if auth_session is not None:
            await _revoke_refresh_family(session, root_session_id=auth_session.id, revoked_at=now)
            await session.commit()
        raise AppError(401, "刷新凭证已失效", "请重新登录。", "refresh_session_invalid")
    user = await session.get(User, token.sub)
    if user is None or not user.active:
        raise AppError(401, "用户不可用", "请重新登录。", "inactive_user")
    auth_session.revoked_at = now
    await _create_refresh_session(
        session,
        request=request,
        response=response,
        user=user,
        rotated_from_id=auth_session.id,
    )
    await session.commit()
    return AuthResponse(
        user=UserPublic.model_validate(user),
        access_expires_in_seconds=settings.access_token_ttl_minutes * 60,
    )


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    session: SessionDep,
    macrolens_refresh: Annotated[str | None, Cookie()] = None,
) -> Response:
    if macrolens_refresh:
        try:
            token = decode_token(macrolens_refresh, TokenType.REFRESH)
            auth_session = await session.get(RefreshSession, token.sid)
            if auth_session:
                await _revoke_refresh_family(
                    session,
                    root_session_id=auth_session.id,
                    revoked_at=datetime.now(UTC),
                )
                await session.commit()
        except AppError:
            pass
    response.delete_cookie("macrolens_access", path="/", domain=settings.cookie_domain)
    response.delete_cookie("macrolens_refresh", path="/", domain=settings.cookie_domain)
    response.status_code = 204
    return response


@router.get("/me", response_model=UserPublic)
async def me(user: CurrentUser) -> UserPublic:
    return UserPublic.model_validate(user)

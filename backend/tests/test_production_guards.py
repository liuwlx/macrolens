from uuid import uuid4

import pytest
from pydantic import ValidationError

from macrolens_api.config import Settings
from macrolens_api.schemas import AIContextInput, AIRunCreate


def test_production_settings_reject_development_defaults() -> None:
    with pytest.raises(ValidationError, match="Unsafe production configuration"):
        Settings(environment="production")


def test_production_settings_accept_hardened_values() -> None:
    settings = Settings(
        environment="production",
        web_origin="https://app.example.com",
        database_url="postgresql+asyncpg://app:strong-password@db.example.com/macrolens",
        database_url_sync="postgresql+psycopg://app:strong-password@db.example.com/macrolens",
        jwt_secret="a-production-secret-with-more-than-32-characters",
        bootstrap_admin_password="a-strong-bootstrap-password",
        cookie_secure=True,
        cookie_samesite="none",
    )
    assert settings.is_production


def test_ai_run_requires_evidence_context() -> None:
    with pytest.raises(ValidationError):
        AIRunCreate(prompt="分析通胀趋势", contexts=[])
    payload = AIRunCreate(
        prompt="分析通胀趋势",
        contexts=[AIContextInput(context_type="series", context_id=uuid4())],
    )
    assert len(payload.contexts) == 1

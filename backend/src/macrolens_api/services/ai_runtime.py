from __future__ import annotations

from ..config import Settings


def ai_runtime_configured(settings: Settings) -> bool:
    return bool(
        settings.openai_api_key
        and settings.openai_model.strip()
        and settings.openai_deep_research_model.strip()
    )

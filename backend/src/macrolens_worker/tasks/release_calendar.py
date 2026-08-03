from __future__ import annotations

import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from macrolens_api.config import get_settings
from macrolens_api.models import Provider, ReleaseDefinition, ReleaseEvent, ReleaseEventSeries, Series

settings = get_settings()

# BLS summaries have changed slightly over time; use conservative substring matching.
BLS_RELEASES: dict[str, tuple[str, str, int, tuple[str, ...]]] = {
    "consumer price index": ("CPI", "消费者价格指数", 5, ("US.CPI.HEADLINE", "US.CPI.CORE")),
    "employment situation": ("EMPLOYMENT", "就业形势", 5, ("US.PAYROLLS", "US.UNEMPLOYMENT")),
    "producer price index": ("PPI", "生产者价格指数", 4, ("US.PPI.FINAL", "US.PPI.CORE")),
    "employment cost index": ("ECI", "就业成本指数", 4, ("US.ECI",)),
    "job openings and labor turnover": ("JOLTS", "职位空缺与劳动力流动", 4, ("US.JOB.OPENINGS",)),
}


def _unfold_ics(raw: str) -> list[str]:
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    unfolded: list[str] = []
    for line in lines:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def parse_ics(raw: str) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in _unfold_ics(raw):
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current is not None:
                events.append(current)
            current = None
            continue
        if current is None or ":" not in line:
            continue
        key, value = line.split(":", 1)
        decoded = (
            value.replace("\\\\", "\\")
            .replace("\\,", ",")
            .replace("\\;", ";")
            .replace("\\n", "\n")
            .replace("\\N", "\n")
        )
        current[key] = decoded
        base_key = key.split(";", 1)[0]
        current.setdefault(base_key, decoded)
    return events


def _event_datetime(event: dict[str, str]) -> datetime | None:
    date_key = next((key for key in event if key.startswith("DTSTART")), None)
    if date_key is None:
        return None
    value = event[date_key]
    tz_match = re.search(r"TZID=([^;:]+)", date_key)
    timezone = ZoneInfo(tz_match.group(1)) if tz_match else UTC
    cleaned = value.rstrip("Z")
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M", "%Y%m%d"):
        try:
            parsed = datetime.strptime(cleaned, fmt).replace(tzinfo=timezone)
            return parsed.astimezone(UTC)
        except ValueError:
            continue
    return None


def _match_release(summary: str) -> tuple[str, str, int, tuple[str, ...]] | None:
    normalized = " ".join(summary.lower().split())
    return next((definition for token, definition in BLS_RELEASES.items() if token in normalized), None)


async def sync_bls_release_calendar(session: AsyncSession) -> dict[str, int]:
    provider = await session.scalar(select(Provider).where(Provider.code == "BLS_API_V2"))
    if provider is None:
        raise RuntimeError("BLS_API_V2 provider is not seeded")
    async with httpx.AsyncClient(
        timeout=45,
        follow_redirects=True,
        headers={"User-Agent": "MacroLens/1.0 research-data-platform"},
    ) as client:
        response = await client.get(settings.bls_release_calendar_url)
        response.raise_for_status()
    parsed_events = parse_ics(response.text)
    if not parsed_events:
        raise RuntimeError("BLS release calendar contained no VEVENT records")
    created = 0
    updated = 0
    linked = 0
    matched_events = 0
    seen_external_ids: set[str] = set()
    for calendar_event in parsed_events:
        summary = calendar_event.get("SUMMARY", "")
        matched = _match_release(summary)
        scheduled_at = _event_datetime(calendar_event)
        if matched is None:
            continue
        if scheduled_at is None:
            raise RuntimeError(f"BLS release event has invalid DTSTART: {calendar_event}")
        matched_events += 1
        code, title_zh, importance, canonical_codes = matched
        definition = await session.scalar(select(ReleaseDefinition).where(ReleaseDefinition.code == code))
        if definition is None:
            definition = ReleaseDefinition(
                code=code,
                provider_id=provider.id,
                name_zh=title_zh,
                name_en=summary,
                release_type="data",
                source_timezone="America/New_York",
                schedule_source_url=settings.bls_release_calendar_url,
            )
            session.add(definition)
            await session.flush()
        external_id = calendar_event.get("UID") or f"bls:{code}:{scheduled_at.isoformat()}"
        if external_id in seen_external_ids:
            raise RuntimeError(
                f"BLS release calendar contains duplicate recognized event id {external_id!r}"
            )
        seen_external_ids.add(external_id)
        event = await session.scalar(select(ReleaseEvent).where(ReleaseEvent.external_event_id == external_id))
        official_url = calendar_event.get("URL") or definition.schedule_source_url
        status = "released" if scheduled_at < datetime.now(UTC) else "scheduled"
        if event is None:
            event = ReleaseEvent(
                release_definition_id=definition.id,
                external_event_id=external_id,
                title_zh=title_zh,
                title_en=summary,
                country_code="US",
                reference_period=None,
                scheduled_at=scheduled_at,
                source_timezone="America/New_York",
                status=status,
                importance_score=importance,
                importance_origin="internal",
                official_url=official_url,
            )
            session.add(event)
            await session.flush()
            created += 1
        else:
            event.scheduled_at = scheduled_at
            event.title_en = summary
            event.status = status if event.actual_released_at is None else "released"
            event.official_url = official_url
            updated += 1
        series_rows = list(
            (
                await session.scalars(select(Series).where(Series.canonical_code.in_(canonical_codes)))
            ).all()
        )
        for series in series_rows:
            mapping = await session.get(
                ReleaseEventSeries,
                {"event_id": event.id, "series_id": series.id, "transform_code": series.default_transform},
            )
            if mapping is None:
                session.add(
                    ReleaseEventSeries(
                        event_id=event.id,
                        series_id=series.id,
                        role="headline",
                        transform_code=series.default_transform,
                        unit_label=series.unit_label_zh,
                    )
                )
                linked += 1
    if matched_events == 0:
        raise RuntimeError("BLS release calendar contained no recognized MacroLens releases")
    await session.commit()
    return {
        "created": created,
        "updated": updated,
        "series_links": linked,
        "matched_events": matched_events,
    }

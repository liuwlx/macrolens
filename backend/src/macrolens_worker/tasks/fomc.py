from __future__ import annotations

import hashlib
import re
from datetime import UTC, date, datetime
from pathlib import PurePosixPath
from urllib.parse import urljoin

import httpx
from lxml import html  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from macrolens_api.config import get_settings
from macrolens_api.models import Document, FomcMeeting, Provider, RawObject
from macrolens_api.services.jobs import enqueue_job
from macrolens_api.services.storage import ObjectStorage

settings = get_settings()
MONTHS = {
    alias: index
    for index, name in enumerate(
        [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ],
        start=1,
    )
    for alias in (name.lower(), name[:3].lower())
}


def _meeting_dates(year: int, month_text: str, date_text: str) -> tuple[date, date] | None:
    month_names = [value.strip().lower() for value in month_text.split("/") if value.strip()]
    if not month_names or any(value not in MONTHS for value in month_names):
        return None
    months = [MONTHS[value] for value in month_names]
    numbers = [int(value) for value in re.findall(r"\d{1,2}", date_text)]
    if not numbers:
        return None
    start_month = months[0]
    end_month = months[1] if len(months) > 1 else start_month
    start_day = numbers[0]
    end_day = numbers[1] if len(numbers) > 1 else numbers[0]
    end_year = year + 1 if end_month < start_month else year
    try:
        return date(year, start_month, start_day), date(end_year, end_month, end_day)
    except ValueError:
        return None


def _parse_calendar_rows(document: html.HtmlElement) -> list[tuple[html.HtmlElement, date, date]]:
    rows = document.xpath(
        "//*[contains(concat(' ', normalize-space(@class), ' '), ' fomc-meeting ')]"
    )
    if not rows:
        raise RuntimeError("Federal Reserve FOMC calendar parser found no meeting rows")
    parsed_rows: list[tuple[html.HtmlElement, date, date]] = []
    failures: list[str] = []
    identities: set[tuple[date, date]] = set()
    for index, row in enumerate(rows, start=1):
        heading_candidates = row.xpath(
            "ancestor::*[contains(@class,'panel')][1]//*[self::h3 or self::h4 or self::h2]/text()"
        )
        year_match = re.search(r"20\d{2}", " ".join(str(value) for value in heading_candidates))
        if not year_match:
            text_before = " ".join(
                row.xpath("preceding::*[self::h2 or self::h3 or self::h4][1]//text()")
            )
            year_match = re.search(r"20\d{2}", text_before)
        if not year_match:
            failures.append(f"row {index}: missing meeting year")
            continue
        year = int(year_match.group(0))
        month_text = " ".join(row.xpath(".//*[contains(@class,'month')]//text()")).strip()
        date_text = " ".join(row.xpath(".//*[contains(@class,'date')]//text()")).strip()
        parsed = _meeting_dates(year, month_text, date_text)
        if parsed is None:
            failures.append(
                f"row {index}: invalid meeting date year={year}, "
                f"month={month_text!r}, date={date_text!r}"
            )
            continue
        if parsed in identities:
            failures.append(f"row {index}: duplicate meeting {parsed[0]}..{parsed[1]}")
            continue
        identities.add(parsed)
        parsed_rows.append((row, parsed[0], parsed[1]))
    if failures:
        raise RuntimeError(
            "Federal Reserve FOMC calendar was only partially parseable; refusing partial "
            "collection: " + "; ".join(failures[:10])
        )
    return parsed_rows


def _document_type(label: str, url: str) -> str:
    text = f"{label} {url}".lower()
    if "minute" in text:
        return "minutes"
    if "projection" in text or "sep" in text:
        return "projection"
    if "press" in text or "transcript" in text:
        return "press_conference"
    if "statement" in text or "a1" in url.lower():
        return "statement"
    return "meeting_material"


async def _persist_raw(
    session: AsyncSession,
    *,
    provider: Provider,
    url: str,
    response: httpx.Response,
    prefix: str,
) -> RawObject:
    now = datetime.now(UTC)
    extension = (
        "pdf"
        if "pdf" in response.headers.get("content-type", "") or url.lower().endswith(".pdf")
        else "html"
    )
    digest = hashlib.sha256(response.content).hexdigest()
    existing = await session.scalar(
        select(RawObject).where(RawObject.provider_id == provider.id, RawObject.sha256 == digest)
    )
    if existing:
        return existing
    key = PurePosixPath(
        "raw",
        prefix,
        f"{now:%Y}",
        f"{now:%m}",
        f"{now:%d}",
        f"{now:%Y%m%dT%H%M%S%fZ}-{digest[:16]}.{extension}",
    ).as_posix()
    stored = await ObjectStorage().put_bytes(
        key,
        response.content,
        response.headers.get("content-type", "application/octet-stream"),
    )
    raw = RawObject(
        provider_id=provider.id,
        object_uri=stored.uri,
        content_type=stored.content_type,
        byte_size=stored.byte_size,
        sha256=stored.sha256,
        request_url=url,
        request_parameters={},
        http_status=response.status_code,
        fetched_at=now,
    )
    session.add(raw)
    await session.flush()
    return raw


async def sync_fomc_calendar(session: AsyncSession) -> dict[str, int]:
    provider = await session.scalar(select(Provider).where(Provider.code == "FEDERAL_RESERVE"))
    if provider is None:
        raise RuntimeError("FEDERAL_RESERVE provider is not seeded")
    async with httpx.AsyncClient(
        timeout=45,
        follow_redirects=True,
        headers={"User-Agent": "MacroLens/1.0 research-data-platform"},
    ) as client:
        response = await client.get(settings.federal_reserve_calendar_url)
        response.raise_for_status()
        await _persist_raw(
            session,
            provider=provider,
            url=str(response.request.url),
            response=response,
            prefix="federal-reserve/fomc-calendar",
        )
        document = html.fromstring(response.content)
        meetings_created = 0
        documents_created = 0
        parsed_rows = _parse_calendar_rows(document)
        parsed_meetings = 0
        material_failures: list[str] = []
        for row, start_date, end_date in parsed_rows:
            parsed_meetings += 1
            meeting = await session.scalar(
                select(FomcMeeting).where(
                    FomcMeeting.meeting_start == start_date,
                    FomcMeeting.meeting_end == end_date,
                )
            )
            if meeting is None:
                meeting = FomcMeeting(
                    meeting_start=start_date,
                    meeting_end=end_date,
                    status="completed" if end_date < date.today() else "scheduled",
                    meeting_type="scheduled",
                    official_url=settings.federal_reserve_calendar_url,
                )
                session.add(meeting)
                await session.flush()
                meetings_created += 1
            else:
                meeting.status = "completed" if end_date < date.today() else "scheduled"
                meeting.official_url = settings.federal_reserve_calendar_url
            anchors = row.xpath(".//a[@href]")
            if end_date < date.today() and not anchors:
                material_failures.append(
                    f"{start_date}..{end_date}: completed meeting has no official material links"
                )
            for anchor in anchors:
                href = str(anchor.get("href") or "").strip()
                if not href or href.startswith("#"):
                    continue
                absolute_url = urljoin(settings.federal_reserve_calendar_url, href)
                label = " ".join(anchor.text_content().split()) or absolute_url.rsplit("/", 1)[-1]
                existing_document = await session.scalar(
                    select(Document).where(Document.source_url == absolute_url)
                )
                if existing_document is None:
                    existing_document = Document(
                        provider_id=provider.id,
                        external_id=absolute_url,
                        document_type=_document_type(label, absolute_url),
                        title=label,
                        title_zh=None,
                        source_url=absolute_url,
                        published_at=datetime.combine(end_date, datetime.min.time(), tzinfo=UTC),
                        language="en",
                        copyright_status="us_government_public",
                        status="processing",
                        metadata_json={"fomc_meeting_id": str(meeting.id)},
                    )
                    session.add(existing_document)
                    await session.flush()
                    documents_created += 1
                try:
                    material = await client.get(absolute_url)
                    material.raise_for_status()
                except httpx.HTTPError as exc:
                    material_failures.append(f"{absolute_url}: {type(exc).__name__}: {exc}")
                    continue
                raw = await _persist_raw(
                    session,
                    provider=provider,
                    url=absolute_url,
                    response=material,
                    prefix="federal-reserve/fomc-documents",
                )
                await enqueue_job(
                    session,
                    job_type="parse_document",
                    payload={
                        "document_id": str(existing_document.id),
                        "raw_object_id": str(raw.id),
                    },
                    idempotency_key=f"parse-fomc:{existing_document.id}:{raw.sha256}",
                    priority=12,
                    max_attempts=3,
                )
        if parsed_meetings == 0:
            raise RuntimeError("Federal Reserve FOMC calendar contained no parseable meetings")
        if material_failures:
            raise RuntimeError(
                "FOMC calendar was parsed but one or more official materials could not be "
                "downloaded; refusing partial collection: " + "; ".join(material_failures[:10])
            )
        await session.commit()
        return {
            "meetings_created": meetings_created,
            "documents_created": documents_created,
            "meetings_parsed": parsed_meetings,
        }

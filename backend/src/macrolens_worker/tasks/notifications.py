from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from macrolens_api.models import (
    AlertRule,
    Document,
    Job,
    Notification,
    ObservationLatest,
    ObservationVintage,
    ReleaseEvent,
    SourceSeries,
)


def _threshold_triggered(value: float, operator: str, target: float) -> bool:
    operations = {
        ">=": value >= target,
        "<=": value <= target,
        ">": value > target,
        "<": value < target,
        "==": value == target,
    }
    return operations.get(operator, False)


def _digest_due(rule: dict[str, object], now: datetime, last_evaluated_at: datetime | None) -> bool:
    if last_evaluated_at is not None and last_evaluated_at.date() == now.date():
        return False
    if "hour_utc" in rule:
        return now.hour == int(rule.get("hour_utc", 0))
    schedule = str(rule.get("schedule", "0 8 * * 1-5")).split()
    if len(schedule) != 5:
        return False
    minute_text, hour_text, _day, _month, weekday_text = schedule
    try:
        minute = int(minute_text)
        hour = int(hour_text)
    except ValueError:
        return False
    if now.hour != hour or not (minute <= now.minute < minute + 15):
        return False
    if weekday_text == "*":
        return True
    allowed: set[int] = set()
    for part in weekday_text.split(","):
        if "-" in part:
            start, end = (int(value) for value in part.split("-", 1))
            allowed.update(range(start, end + 1))
        else:
            allowed.add(int(part))
    # Cron uses Sunday=0/7. Python uses Monday=0.
    cron_weekday = (now.weekday() + 1) % 7
    return cron_weekday in allowed or (cron_weekday == 0 and 7 in allowed)


async def evaluate_alerts(session: AsyncSession, *, workspace_id: UUID | None = None) -> dict[str, int]:
    stmt = select(AlertRule).where(AlertRule.active.is_(True))
    if workspace_id:
        stmt = stmt.where(AlertRule.workspace_id == workspace_id)
    alerts = list((await session.scalars(stmt)).all())
    created = 0
    now = datetime.now(UTC)
    for alert in alerts:
        triggered = False
        title = alert.name
        body = ""
        action_url: str | None = None
        payload: dict[str, object] = {}
        cooldown_hours = float(alert.rule.get("cooldown_hours", 1))

        if alert.alert_type == "release_reminder" and alert.target_id:
            event = await session.get(ReleaseEvent, alert.target_id)
            minutes = int(alert.rule.get("minutes_before", 30))
            if event and now <= event.scheduled_at <= now + timedelta(minutes=minutes):
                triggered = True
                body = f"{event.title_zh} 将于 {event.scheduled_at.isoformat()} 发布。"
                action_url = f"/calendar?event={event.id}"
                payload = {"release_event_id": str(event.id), "scheduled_at": event.scheduled_at.isoformat()}

        elif alert.alert_type in {"threshold", "revision"} and alert.target_id:
            source = await session.scalar(
                select(SourceSeries).where(
                    SourceSeries.series_id == alert.target_id,
                    SourceSeries.is_primary.is_(True),
                    SourceSeries.mapping_status == "verified",
                )
            )
            if source and alert.alert_type == "threshold":
                latest = await session.scalar(
                    select(ObservationLatest)
                    .where(ObservationLatest.source_series_id == source.id)
                    .order_by(ObservationLatest.period_start.desc())
                    .limit(1)
                )
                threshold = alert.rule.get("value")
                operator = str(alert.rule.get("operator", ">="))
                if latest and latest.value is not None and threshold is not None:
                    target = float(threshold)
                    value = float(latest.value)
                    triggered = _threshold_triggered(value, operator, target)
                    cooldown_hours = float(alert.rule.get("cooldown_hours", 24))
                    if triggered:
                        body = f"最新值 {value} 已满足条件 {operator} {target}。"
                        action_url = f"/data?series={alert.target_id}"
                        payload = {
                            "series_id": str(alert.target_id),
                            "period_start": latest.period_start.isoformat(),
                            "value": value,
                            "operator": operator,
                            "threshold": target,
                        }
            elif source and alert.last_evaluated_at is not None:
                revision = await session.scalar(
                    select(ObservationVintage)
                    .where(
                        ObservationVintage.source_series_id == source.id,
                        ObservationVintage.observation_status == "revised",
                        ObservationVintage.vintage_at > alert.last_evaluated_at,
                    )
                    .order_by(ObservationVintage.vintage_at.desc())
                    .limit(1)
                )
                if revision:
                    triggered = True
                    body = f"{revision.period_start.isoformat()} 的历史数据已修订。"
                    action_url = f"/data?series={alert.target_id}"
                    payload = {
                        "series_id": str(alert.target_id),
                        "period_start": revision.period_start.isoformat(),
                        "vintage_at": revision.vintage_at.isoformat(),
                    }

        elif alert.alert_type == "new_document" and alert.last_evaluated_at is not None:
            document_stmt = select(Document).where(Document.created_at > alert.last_evaluated_at)
            provider_code = alert.rule.get("provider_code")
            document_type = alert.rule.get("document_type")
            if provider_code:
                from macrolens_api.models import Provider

                document_stmt = document_stmt.join(Provider, Provider.id == Document.provider_id).where(
                    Provider.code == str(provider_code)
                )
            if document_type:
                document_stmt = document_stmt.where(Document.document_type == str(document_type))
            document = await session.scalar(document_stmt.order_by(Document.created_at.desc()).limit(1))
            if document:
                triggered = True
                body = f"发现新文档：{document.title_zh or document.title}。"
                action_url = f"/documents?document={document.id}"
                payload = {"document_id": str(document.id), "document_type": document.document_type}

        elif alert.alert_type == "fomc_update" and alert.last_evaluated_at is not None:
            document_stmt = select(Document).where(
                Document.created_at > alert.last_evaluated_at,
                Document.document_type.in_(["statement", "minutes", "projection", "press_conference", "meeting_material"]),
            )
            if alert.target_id:
                document_stmt = document_stmt.where(
                    Document.metadata_json.contains({"fomc_meeting_id": str(alert.target_id)})
                )
            document = await session.scalar(document_stmt.order_by(Document.created_at.desc()).limit(1))
            if document:
                triggered = True
                body = f"FOMC材料已更新：{document.title_zh or document.title}。"
                action_url = f"/fomc?meeting={alert.target_id}" if alert.target_id else "/fomc"
                payload = {"document_id": str(document.id), "fomc_meeting_id": str(alert.target_id) if alert.target_id else None}

        elif alert.alert_type == "digest" and _digest_due(alert.rule, now, alert.last_evaluated_at):
            triggered = True
            body = "今日宏观数据与事件摘要已准备。"
            action_url = "/"
            cooldown_hours = 20

        if triggered:
            duplicate = await session.scalar(
                select(Notification.id).where(
                    Notification.alert_rule_id == alert.id,
                    Notification.created_at >= now - timedelta(hours=max(cooldown_hours, 0.25)),
                )
            )
            if duplicate is None:
                notification = Notification(
                    workspace_id=alert.workspace_id,
                    user_id=alert.owner_user_id,
                    alert_rule_id=alert.id,
                    notification_type=alert.alert_type,
                    title=title,
                    body=body,
                    action_url=action_url,
                    payload=payload,
                )
                session.add(notification)
                await session.flush()
                if "email" in (alert.channels or []):
                    session.add(
                        Job(
                            job_type="send_email_notification",
                            payload={"notification_id": str(notification.id)},
                            idempotency_key=f"email-notification:{notification.id}",
                            priority=1,
                            max_attempts=5,
                        )
                    )
                created += 1
        alert.last_evaluated_at = now
    await session.commit()
    return {"created": created}

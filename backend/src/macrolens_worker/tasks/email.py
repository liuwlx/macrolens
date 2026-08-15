from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from macrolens_api.config import get_settings
from macrolens_api.models import Notification, User

settings = get_settings()


def _deliver(message: EmailMessage) -> None:
    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST is not configured")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as client:
        if settings.smtp_use_tls:
            client.starttls()
        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password or "")
        client.send_message(message)


async def send_email_notification(
    session: AsyncSession, *, notification_id: UUID
) -> dict[str, str]:
    notification = await session.get(Notification, notification_id)
    if notification is None:
        raise RuntimeError(f"Notification not found: {notification_id}")
    user = await session.get(User, notification.user_id)
    if user is None or not user.active:
        raise RuntimeError("Notification recipient is unavailable")

    message = EmailMessage()
    message["Subject"] = f"MacroLens：{notification.title}"
    message["From"] = settings.smtp_from
    message["To"] = user.email
    action = (
        f"\n\n查看：{settings.web_origin}{notification.action_url}"
        if notification.action_url
        else ""
    )
    message.set_content(
        f"{notification.body or notification.title}{action}\n\n"
        "本邮件由 MacroLens 提醒规则自动发送。"
    )
    await asyncio.to_thread(_deliver, message)
    return {"recipient": user.email, "notification_id": str(notification.id)}

"""Transactional email behind a small provider interface: console (dev), SMTP, Resend. Every send is logged."""
import logging
import smtplib
import uuid
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import make_msgid

import httpx
from sqlalchemy.orm import Session

from ..emails import templates
from ..models import EmailLog, EmailStatus
from ..settings import get_settings

log = logging.getLogger("email")


@dataclass
class Message:
    to: str
    subject: str
    html: str
    text: str


class EmailProvider:
    name = "base"

    def send(self, msg: Message) -> str:
        """Send and return the provider's message id. Raise on failure."""
        raise NotImplementedError


class ConsoleProvider(EmailProvider):
    """Development: prints the message (with links) to the log instead of sending."""
    name = "console"
    outbox: list[Message] = []  # tests read this

    def send(self, msg: Message) -> str:
        ConsoleProvider.outbox.append(msg)
        log.info("EMAIL to=%s subject=%s\n%s", msg.to, msg.subject, msg.text)
        return f"console-{uuid.uuid4().hex[:12]}"


class SmtpProvider(EmailProvider):
    name = "smtp"

    def send(self, msg: Message) -> str:
        s = get_settings()
        em = EmailMessage()
        em["From"], em["To"], em["Subject"] = s.email_from, msg.to, msg.subject
        if s.email_reply_to:
            em["Reply-To"] = s.email_reply_to
        em["Message-ID"] = make_msgid()
        em.set_content(msg.text)
        em.add_alternative(msg.html, subtype="html")
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as smtp:
            if s.smtp_starttls:
                smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(em)
        return em["Message-ID"]


class ResendProvider(EmailProvider):
    name = "resend"

    def send(self, msg: Message) -> str:
        s = get_settings()
        body = {"from": s.email_from, "to": [msg.to], "subject": msg.subject, "html": msg.html, "text": msg.text}
        if s.email_reply_to:
            body["reply_to"] = s.email_reply_to
        r = httpx.post("https://api.resend.com/emails", json=body, timeout=20,
                       headers={"Authorization": f"Bearer {s.resend_api_key}"})
        r.raise_for_status()
        return r.json().get("id", "")


def get_provider() -> EmailProvider:
    name = get_settings().email_provider
    return {"smtp": SmtpProvider, "resend": ResendProvider}.get(name, ConsoleProvider)()


def send_template(db: Session, template: str, to: str, context: dict, user_id=None) -> EmailLog:
    """Render a template, send it, and record the outcome. Never raises: a failed email must not fail the request."""
    subject, html, text = templates.render(template, context)
    provider = get_provider()
    entry = EmailLog(to=to, template=template, subject=subject, provider=provider.name, user_id=user_id,
                     status=EmailStatus.SENT)
    try:
        entry.provider_id = provider.send(Message(to=to, subject=subject, html=html, text=text)) or ""
    except Exception as e:  # noqa: BLE001
        log.exception("email send failed (%s to %s)", template, to)
        entry.status, entry.error = EmailStatus.FAILED, f"{type(e).__name__}: {e}"[:2000]
    db.add(entry)
    db.commit()
    return entry

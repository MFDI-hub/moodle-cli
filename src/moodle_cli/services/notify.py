"""Send a sync summary to Telegram, Discord, ntfy, mail, or XMPP."""

from __future__ import annotations

import json
import smtplib
from email.message import EmailMessage
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from moodle_cli.config.manager import NotifySettings
from moodle_cli.exceptions import MoodleError
from moodle_cli.services.sync import SyncReport


def format_report(reports: list[SyncReport]) -> str:
    downloaded = sum(len(item.downloaded) for item in reports)
    linked = sum(len(item.linked) for item in reports)
    skipped = sum(len(item.skipped) for item in reports)
    removed = sum(len(item.removed) for item in reports)
    errors = sum(len(item.errors) for item in reports)
    lines = [
        f"Moodle sync: {downloaded} new, {linked} linked, {skipped} unchanged, "
        f"{removed} kept after server delete, {errors} errors."
    ]
    for report in reports:
        for path in report.downloaded[:20]:
            lines.append(f"+ {path}")
        if len(report.downloaded) > 20:
            lines.append(f"+ … {len(report.downloaded) - 20} more")
    return "\n".join(lines)


def notify(settings: NotifySettings, reports: list[SyncReport]) -> list[str]:
    if not any(len(item.downloaded) or len(item.linked) for item in reports):
        return []
    text = format_report(reports)
    sent: list[str] = []
    if settings.telegram_token and settings.telegram_chat_id:
        _telegram(settings, text)
        sent.append("telegram")
    if settings.discord_webhook:
        _discord(settings, text)
        sent.append("discord")
    if settings.ntfy_topic:
        _ntfy(settings, text)
        sent.append("ntfy")
    if settings.mail_host and settings.mail_to:
        _mail(settings, text)
        sent.append("mail")
    if settings.xmpp_jid and settings.xmpp_to:
        _xmpp(settings, text)
        sent.append("xmpp")
    return sent


def _http_url(url: str) -> str:
    if not url.startswith(("https://", "http://")):
        raise MoodleError(f"Refusing non-HTTP URL: {url}")
    return url


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> None:
    data = json.dumps(payload).encode()
    req = Request(_http_url(url), data=data, method="POST")  # noqa: S310
    req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    with urlopen(req, timeout=30) as resp:  # noqa: S310
        resp.read()


def _telegram(settings: NotifySettings, text: str) -> None:
    url = f"https://api.telegram.org/bot{settings.telegram_token}/sendMessage"
    _post_json(url, {"chat_id": settings.telegram_chat_id, "text": text})


def _discord(settings: NotifySettings, text: str) -> None:
    _post_json(settings.discord_webhook, {"content": text[:2000]})


def _ntfy(settings: NotifySettings, text: str) -> None:
    base = (settings.ntfy_url or "https://ntfy.sh").rstrip("/")
    url = f"{base}/{quote(settings.ntfy_topic)}"
    req = Request(_http_url(url), data=text.encode(), method="POST")  # noqa: S310
    req.add_header("Title", "Moodle sync")
    with urlopen(req, timeout=30) as resp:  # noqa: S310
        resp.read()


def _mail(settings: NotifySettings, text: str) -> None:
    message = EmailMessage()
    message["Subject"] = "Moodle sync"
    message["From"] = settings.mail_from or settings.mail_username or settings.mail_to
    message["To"] = settings.mail_to
    message.set_content(text)
    with smtplib.SMTP(settings.mail_host, settings.mail_port, timeout=30) as smtp:
        smtp.starttls()
        if settings.mail_username:
            smtp.login(settings.mail_username, settings.mail_password)
        smtp.send_message(message)


def _xmpp(settings: NotifySettings, text: str) -> None:
    try:
        import slixmpp
    except ImportError as exc:
        raise MoodleError(
            "XMPP notifications need the notify extra: pip install 'moodle-cli[notify]'"
        ) from exc

    class Sender(slixmpp.ClientXMPP):
        def __init__(self) -> None:
            super().__init__(settings.xmpp_jid, settings.xmpp_password)
            self.add_event_handler("session_start", self._start)

        async def _start(self, _event: Any) -> None:
            self.send_message(mto=settings.xmpp_to, mbody=text, mtype="chat")
            self.disconnect()

    client = Sender()
    client.connect()
    client.process(forever=False)

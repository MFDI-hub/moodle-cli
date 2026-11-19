"""Course backup and restore through the Moodle backup UI (cookie session)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from moodle_cli._utils import require_session
from moodle_cli.client.pages import filename, html_text
from moodle_cli.exceptions import MoodleError
from moodle_cli.services.base import BaseService

_HIDDEN = re.compile(r'(?is)<input\b[^>]*\btype="hidden"[^>]*>')
_ATTR = re.compile(r"""(?is)\b(\w+)\s*=\s*["']([^"']*)["']""")
_MBZ = re.compile(r'(?i)href="([^"]+\.mbz[^"]*)"')


def _hidden_fields(html: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for tag in _HIDDEN.findall(html):
        attrs = dict(_ATTR.findall(tag))
        name = attrs.get("name")
        if name:
            fields[name] = attrs.get("value", "")
    return fields


class BackupService(BaseService):
    def backup_course(self, course_id: int, dest: str | Path) -> Path:
        session = require_session(self.client)
        session._ensure()
        start = f"{session.base_url}/backup/backup.php?id={course_id}"
        page = session.session.get(start)
        page.raise_for_status()
        data = _hidden_fields(page.text)
        data.setdefault("id", str(course_id))
        data.setdefault("sesskey", session.sesskey)
        data.setdefault("setting_root_users", "0")
        data["submitbutton"] = "Jump to final step"
        confirm = session.session.post(
            f"{session.base_url}/backup/backup.php", data=data, allow_redirects=True
        )
        confirm.raise_for_status()
        final = _hidden_fields(confirm.text)
        final.setdefault("id", str(course_id))
        final.setdefault("sesskey", session.sesskey)
        done = session.session.post(
            str(getattr(confirm, "url", start)), data=final, allow_redirects=True
        )
        done.raise_for_status()
        match = _MBZ.search(done.text)
        if not match:
            raise MoodleError("Backup finished but no .mbz download link was found.")
        href = match.group(1)
        if not href.startswith("http"):
            href = f"{session.base_url}/{href.lstrip('/')}"
        download = session.session.get(href)
        download.raise_for_status()
        path = Path(dest)
        if path.is_dir() or str(dest).endswith(("/", "\\")):
            path.mkdir(parents=True, exist_ok=True)
            path = path / filename(str(getattr(download, "url", href)), "")
            if path.suffix.lower() != ".mbz":
                path = path.with_suffix(".mbz")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(download.content)
        return path

    def restore_course(self, mbz_path: str | Path, category_id: int) -> dict[str, Any]:
        session = require_session(self.client)
        session._ensure()
        path = Path(mbz_path)
        url = f"{session.base_url}/backup/restorefile.php"
        files = {"file": (path.name, path.read_bytes())}
        data = {"sesskey": session.sesskey, "categoryid": str(category_id), "action": "upload"}
        resp = session.session.post(url, data=data, files=files, allow_redirects=True)
        resp.raise_for_status()
        return {
            "ok": True,
            "url": str(getattr(resp, "url", url)),
            "title": html_text(resp.text)[:200],
        }

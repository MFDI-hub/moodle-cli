"""Incremental course mirror: SQLite state, submissions, books, optional externals."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from moodle_cli._utils import file_save_name, host_of, safe_name
from moodle_cli.exceptions import MoodleAPIError
from moodle_cli.services.assign import AssignService
from moodle_cli.services.book import BookService
from moodle_cli.services.file import FileService

if TYPE_CHECKING:
    from collections.abc import Callable

    from moodle_cli.api.models import Course

_EXTERNAL_HINTS = (
    "youtube.com",
    "youtu.be",
    "opencast",
    "kaltura",
    "owncloud",
    "sciebo",
    "drive.google",
    "docs.google",
    "helix",
)


@dataclass
class SyncItem:
    url: str
    name: str
    course_id: int
    kind: str = "moodle"  # moodle | submission | book | external
    size: int = 0
    time_modified: int = 0
    body: str = ""


@dataclass
class SyncReport:
    dest: Path
    downloaded: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    linked: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dest": str(self.dest),
            "downloaded": self.downloaded,
            "skipped": self.skipped,
            "linked": self.linked,
            "removed": self.removed,
            "errors": self.errors,
        }


class SyncStore:
    """SQLite index of mirrored files. Local copies of removed server files stay."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                url TEXT PRIMARY KEY,
                course_id INTEGER,
                local_path TEXT,
                size INTEGER,
                timemodified INTEGER,
                sha256 TEXT,
                status TEXT
            )
            """
        )
        self.conn.commit()

    def get(self, url: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM files WHERE url = ?", (url,)).fetchone()

    def upsert(
        self,
        url: str,
        course_id: int,
        local_path: str,
        size: int,
        time_modified: int,
        sha256: str,
        status: str = "present",
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO files (url, course_id, local_path, size, timemodified, sha256, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                course_id=excluded.course_id,
                local_path=excluded.local_path,
                size=excluded.size,
                timemodified=excluded.timemodified,
                sha256=excluded.sha256,
                status=excluded.status
            """,
            (url, course_id, local_path, size, time_modified, sha256, status),
        )
        self.conn.commit()

    def mark_removed(self, live_urls: set[str], course_id: int) -> list[str]:
        rows = self.conn.execute(
            "SELECT url, local_path FROM files WHERE course_id = ? AND status = 'present'",
            (course_id,),
        ).fetchall()
        gone: list[str] = []
        for row in rows:
            if row["url"] not in live_urls:
                self.conn.execute(
                    "UPDATE files SET status = 'removed' WHERE url = ?",
                    (row["url"],),
                )
                gone.append(row["local_path"])
        self.conn.commit()
        return gone

    def close(self) -> None:
        self.conn.close()


def collect_items(course: Course, *, submissions: bool = True) -> list[SyncItem]:
    items: list[SyncItem] = []
    seen: set[str] = set()

    def add(item: SyncItem) -> None:
        if not item.url or item.url in seen:
            return
        seen.add(item.url)
        items.append(item)

    for ref in course.files:
        kind = "moodle" if ref.is_moodle else "external"
        add(SyncItem(url=ref.url, name=ref.name, course_id=course.id, kind=kind))

    if submissions:
        assign = AssignService(course._api.client)
        for assignment in course.assignments:
            for ref in assign.submission_files(assignment.id):
                add(
                    SyncItem(
                        url=ref["url"],
                        name=ref["name"],
                        course_id=course.id,
                        kind="submission",
                        size=int(ref.get("size") or 0),
                        time_modified=int(ref.get("timemodified") or 0),
                    )
                )

    books = BookService(course._api.client)
    for activity in course.of("book"):
        try:
            chapters = books.chapters(
                activity.id, activity.instance, activity.url, course_id=course.id
            )
        except MoodleAPIError as exc:
            items.append(
                SyncItem(
                    url=activity.url or f"book:{activity.id}",
                    name=activity.name,
                    course_id=course.id,
                    kind="book",
                    body=f"Could not read book: {exc}",
                )
            )
            continue
        for chapter in chapters:
            add(
                SyncItem(
                    url=chapter["url"],
                    name=chapter["name"],
                    course_id=course.id,
                    kind="book",
                    body=chapter.get("html") or "",
                )
            )
    return items


def unique_path(folder: Path, name: str, used: set[str]) -> Path:
    target = folder / name
    stem, suffix = target.stem, target.suffix
    index = 1
    while str(target) in used:
        index += 1
        target = folder / f"{stem}_{index}{suffix}"
    used.add(str(target))
    return target


def is_external_media(url: str) -> bool:
    host = host_of(url)
    return any(hint in host or hint in url.lower() for hint in _EXTERNAL_HINTS)


def download_external(url: str, dest: Path) -> Path | None:
    try:
        import yt_dlp
    except ImportError:
        dest.write_text(url + "\n", encoding="utf-8")
        return None
    options = {
        "outtmpl": str(dest.with_suffix("")) + ".%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([url])
    matches = list(dest.parent.glob(dest.stem + ".*"))
    return matches[0] if matches else dest


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sync_course(
    course: Course,
    dest: Path,
    store: SyncStore,
    *,
    submissions: bool = True,
    external: bool = False,
    folder_name: str | None = None,
    on_saved: Callable[[str], None] | None = None,
) -> SyncReport:
    folder = dest / safe_name(folder_name or course.short_name)
    folder.mkdir(parents=True, exist_ok=True)
    report = SyncReport(dest=folder)
    files_dir = folder / "files"
    files_dir.mkdir(exist_ok=True)
    used: set[str] = set()
    live: set[str] = set()
    file_svc = FileService(course._api.client)

    for item in collect_items(course, submissions=submissions):
        live.add(item.url)
        name = file_save_name(item.name, item.url)
        if item.kind == "book":
            name = file_save_name(item.name or "chapter", "")
            if not name.lower().endswith((".html", ".htm", ".md")):
                name = f"{Path(name).stem}.html"
        elif item.kind == "external":
            parsed = urlparse(item.url)
            suffix = Path(parsed.path).suffix
            if not suffix:
                suffix = ".url"
            name = file_save_name(item.name or parsed.path or "link", "")
            if "." not in Path(name).name:
                name = f"{name}{suffix}"
        target = unique_path(files_dir, name, used)
        row = store.get(item.url)
        if (
            row
            and row["status"] == "present"
            and Path(row["local_path"]).exists()
            and (
                (
                    item.size
                    and item.size == row["size"]
                    and item.time_modified == row["timemodified"]
                )
                or (not item.size and Path(row["local_path"]).stat().st_size > 0)
            )
        ):
            report.skipped.append(row["local_path"])
            continue
        try:
            if item.kind == "book":
                data = (item.body or "").encode("utf-8")
                target.write_bytes(data)
                digest = sha256_bytes(data)
                size = len(data)
            elif item.kind == "external":
                if not external:
                    link = target.with_suffix(".url")
                    link.write_text(item.url + "\n", encoding="utf-8")
                    report.linked.append(str(link))
                    store.upsert(
                        item.url, course.id, str(link), link.stat().st_size, 0, "", "present"
                    )
                    continue
                if is_external_media(item.url):
                    saved = download_external(item.url, target)
                    if saved is None:
                        link = target.with_suffix(".url")
                        if not link.exists():
                            link.write_text(item.url + "\n", encoding="utf-8")
                        report.linked.append(str(link))
                        store.upsert(
                            item.url, course.id, str(link), link.stat().st_size, 0, "", "present"
                        )
                        continue
                    target = saved
                else:
                    result = file_svc.download(item.url, str(target))
                    target = Path(result["path"])
                digest = sha256_bytes(target.read_bytes()) if target.exists() else ""
                size = target.stat().st_size if target.exists() else 0
            else:
                result = file_svc.download(item.url, str(target))
                target = Path(result["path"])
                digest = sha256_bytes(target.read_bytes())
                size = target.stat().st_size
            store.upsert(
                item.url,
                course.id,
                str(target),
                size,
                item.time_modified,
                digest,
                "present",
            )
            report.downloaded.append(str(target))
            if on_saved is not None:
                on_saved(str(target))
        except Exception as exc:
            report.errors.append(f"{item.url}: {exc}")
            if item.kind == "external":
                link = target.with_suffix(".url")
                link.write_text(item.url + "\n", encoding="utf-8")
                report.linked.append(str(link))

    report.removed.extend(store.mark_removed(live, course.id))
    return report

"""Book chapters — list plus HTML, from web services or the book page."""

from __future__ import annotations

from typing import Any

from moodle_cli.client.pages import class_inner, parse_book_chapters
from moodle_cli.client.session import MoodleSessionClient
from moodle_cli.services.base import BaseService
from moodle_cli.services.content import ContentService


class BookService(BaseService):
    def chapters(
        self,
        cmid: int,
        book_id: int = 0,
        view_url: str = "",
        course_id: int = 0,
    ) -> list[dict[str, Any]]:
        """Chapter titles and HTML for a book activity."""
        if isinstance(self.client, MoodleSessionClient):
            return self._from_page(cmid, view_url)
        if course_id:
            rows = ContentService(self.client).list_activities("book", course_id)
            match = next(
                (
                    row
                    for row in rows
                    if int(row.get("coursemodule") or 0) == cmid
                    or (book_id and int(row.get("id") or 0) == book_id)
                ),
                None,
            )
            contents = (match or {}).get("contents") or (match or {}).get("chapters") or []
            chapters: list[dict[str, Any]] = []
            for index, row in enumerate(contents):
                if not isinstance(row, dict):
                    continue
                name = str(row.get("filename") or row.get("title") or f"Chapter {index + 1}")
                html = str(row.get("content") or row.get("html") or "")
                url = str(row.get("fileurl") or row.get("url") or f"{view_url}#chapter-{index}")
                chapters.append({"name": name, "url": url, "html": html})
            if chapters:
                return chapters
        if view_url and isinstance(self.client, MoodleSessionClient):
            return self._from_page(cmid, view_url)
        return []

    def _from_page(self, cmid: int, view_url: str) -> list[dict[str, Any]]:
        session = self.client
        if not isinstance(session, MoodleSessionClient):
            return []
        session._ensure()
        url = view_url or f"{session.base_url}/mod/book/view.php?id={cmid}"
        resp = session.session.get(url)
        resp.raise_for_status()
        chapters = parse_book_chapters(resp.text, session.base_url)
        out: list[dict[str, Any]] = []
        for chapter in chapters:
            page = session.session.get(chapter["url"])
            page.raise_for_status()
            out.append(
                {
                    "name": chapter["name"],
                    "url": chapter["url"],
                    "html": _book_body(page.text),
                    "id": chapter.get("id"),
                }
            )
        if out:
            return out
        return [{"name": "Book", "url": url, "html": _book_body(resp.text)}]


def _book_body(page_html: str) -> str:
    return (
        class_inner(page_html, "book_content") or class_inner(page_html, "region-main") or page_html
    )

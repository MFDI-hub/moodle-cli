"""Activity-content services — read the *contents* of activities the `content`
group can only list (workshop, glossary, database, wiki, lesson).

These complete the "list an activity, then read what's inside it" story. Every
function here is a pure read (`_get_`), no view-event, no mutation.
"""

from __future__ import annotations

from typing import Any

from moodle_cli.services.base import BaseService


class WorkshopService(BaseService):
    def add_submission(self, workshop_id: int, title: str, content: str) -> Any:
        return self.call(
            "mod_workshop_add_submission",
            workshopid=workshop_id,
            title=title,
            content=content,
        )

    def submissions(self, workshop_id: int) -> list[dict[str, Any]]:
        data = self.call("mod_workshop_get_submissions", workshopid=workshop_id)
        subs: list[dict[str, Any]] = data.get("submissions", []) if isinstance(data, dict) else []
        return subs

    def grades_report(self, workshop_id: int) -> dict[str, Any]:
        data = self.call("mod_workshop_get_grades_report", workshopid=workshop_id)
        report: dict[str, Any] = data.get("report", data) if isinstance(data, dict) else {}
        return report


class GlossaryService(BaseService):
    def add_entry(self, glossary_id: int, concept: str, definition: str) -> Any:
        return self.call(
            "mod_glossary_add_entry",
            glossaryid=glossary_id,
            concept=concept,
            definition=definition,
            definitionformat=1,
        )

    def entries(self, glossary_id: int, letter: str = "ALL") -> list[dict[str, Any]]:
        data = self.call("mod_glossary_get_entries_by_letter", id=glossary_id, letter=letter)
        entries: list[dict[str, Any]] = data.get("entries", []) if isinstance(data, dict) else []
        return entries


class DatabaseService(BaseService):
    def add_entry(self, database_id: int, data: list[dict[str, Any]]) -> Any:
        return self.call("mod_data_add_entry", databaseid=database_id, data=data)

    def entries(self, database_id: int) -> list[dict[str, Any]]:
        data = self.call("mod_data_get_entries", databaseid=database_id)
        entries: list[dict[str, Any]] = data.get("entries", []) if isinstance(data, dict) else []
        return entries


class WikiService(BaseService):
    def new_page(self, subwiki_id: int, title: str, content: str) -> Any:
        return self.call(
            "mod_wiki_new_page",
            subwikiid=subwiki_id,
            title=title,
            content=content,
        )

    def edit_page(self, page_id: int, content: str, section: str | None = None) -> Any:
        params: dict[str, Any] = {"pageid": page_id, "content": content}
        if section is not None:
            params["section"] = section
        return self.call("mod_wiki_edit_page", **params)

    def subwiki_pages(self, subwiki_id: int) -> list[dict[str, Any]]:
        data = self.call("mod_wiki_get_subwiki_pages", subwikiid=subwiki_id)
        pages: list[dict[str, Any]] = data.get("pages", []) if isinstance(data, dict) else []
        return pages

    def page_contents(self, page_id: int) -> dict[str, Any]:
        data = self.call("mod_wiki_get_page_contents", pageid=page_id)
        page: dict[str, Any] = data.get("page", data) if isinstance(data, dict) else {}
        return page


class LessonService(BaseService):
    def page_data(self, lesson_id: int, page_id: int) -> dict[str, Any]:
        data: dict[str, Any] = self.call(
            "mod_lesson_get_page_data", lessonid=lesson_id, pageid=page_id
        )
        return data

    def process_page(self, lesson_id: int, page_id: int, answers: dict[str, Any]) -> Any:
        return self.call(
            "mod_lesson_process_page",
            lessonid=lesson_id,
            pageid=page_id,
            data=[{"name": key, "value": value} for key, value in answers.items()],
        )

    def pages(self, lesson_id: int) -> list[dict[str, Any]]:
        data = self.call("mod_lesson_get_pages", lessonid=lesson_id)
        pages: list[dict[str, Any]] = data.get("pages", []) if isinstance(data, dict) else []
        return pages

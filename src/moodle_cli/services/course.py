"""Course service."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from moodle_cli.services.base import BaseService, MoodleModel


class CourseRecord(MoodleModel):
    id: int
    short_name: Annotated[str, Field(validation_alias="shortname")]
    full_name: Annotated[str, Field(validation_alias="fullname")]
    category_id: Annotated[int, Field(validation_alias="categoryid")] = 0
    summary: str = ""
    visible: int = 1
    format: str = "topics"
    start_date: Annotated[int, Field(validation_alias="startdate")] = 0
    end_date: Annotated[int, Field(validation_alias="enddate")] = 0


class CourseContent(MoodleModel):
    id: int
    name: str
    summary: str = ""
    table: list[dict[str, Any]] = []
    modules: list[dict[str, Any]] = []


class CategoryRecord(MoodleModel):
    id: int
    name: str = ""
    parent: int = 0
    course_count: Annotated[int, Field(validation_alias="coursecount")] = 0
    depth: int = 0
    visible: int = 1


class CourseService(BaseService):
    def list_courses(self) -> list[CourseRecord]:
        data = self.call("core_course_get_courses")
        return [CourseRecord.model_validate(c) for c in data]

    def get_categories(self) -> list[CategoryRecord]:
        data = self.call("core_course_get_categories")
        return [CategoryRecord.model_validate(c) for c in data]

    def get_module(self, cmid: int) -> dict[str, Any]:
        """Course-module metadata by course-module id (core_course_get_course_module)."""
        data = self.call("core_course_get_course_module", cmid=cmid)
        cm: dict[str, Any] = data.get("cm", data)
        return cm

    def get_timeline(self, classification: str = "all") -> list[CourseRecord]:
        """Enrolled courses by timeline status — inprogress / past / future / all
        (core_course_get_enrolled_courses_by_timeline_classification)."""
        data = self.call(
            "core_course_get_enrolled_courses_by_timeline_classification",
            classification=classification,
        )
        return [CourseRecord.model_validate(c) for c in data.get("courses", [])]

    def get_course(self, course_id: int) -> CourseRecord:
        data = self.call("core_course_get_courses", options={"ids": [course_id]})
        return CourseRecord.model_validate(data[0])

    def search_courses(self, query: str) -> list[CourseRecord]:
        data = self.call(
            "core_course_search_courses",
            criterianame="search",
            criteriavalue=query,
        )
        return [CourseRecord.model_validate(c) for c in data.get("courses", [])]

    def get_contents(self, course_id: int) -> list[CourseContent]:
        data = self.call("core_course_get_contents", courseid=course_id)
        return [CourseContent.model_validate(s) for s in data]

    def create_course(
        self,
        full_name: str,
        short_name: str,
        category_id: int,
        **kwargs: Any,
    ) -> CourseRecord:
        course_data = {"fullname": full_name, "shortname": short_name, "categoryid": category_id}
        course_data.update(kwargs)
        data = self.call("core_course_create_courses", courses=[course_data])
        return CourseRecord.model_validate(data[0])

    def update_course(
        self, course_id: int, custom_fields: list[dict[str, Any]] | None = None, **kwargs: Any
    ) -> None:
        course_data: dict[str, Any] = {"id": course_id, **kwargs}
        if custom_fields:
            course_data["customfields"] = custom_fields
        self.call("core_course_update_courses", courses=[course_data])

    def delete_courses(self, course_ids: list[int]) -> None:
        self.call("core_course_delete_courses", courseids=course_ids)

    def create_categories(
        self, name: str, parent: int = 0, description: str = ""
    ) -> list[dict[str, Any]]:
        data = self.call(
            "core_course_create_categories",
            categories=[{"name": name, "parent": parent, "description": description}],
        )
        return list(data) if isinstance(data, list) else [data]

    def update_categories(self, category_id: int, **kwargs: Any) -> None:
        self.call(
            "core_course_update_categories",
            categories=[{"id": category_id, **kwargs}],
        )

    def delete_categories(self, category_ids: list[int], recursive: int = 1) -> None:
        self.call(
            "core_course_delete_categories",
            categories=[{"id": cid, "recursive": recursive} for cid in category_ids],
        )

    def ensure_course(
        self,
        short_name: str,
        full_name: str,
        category_id: int,
        update: bool = False,
    ) -> tuple[CourseRecord, bool]:
        """Return the course with this shortname, creating it when missing."""
        for course in self.list_courses():
            if course.short_name == short_name:
                if update:
                    self.update_course(course.id, fullname=full_name, categoryid=category_id)
                    return self.get_course(course.id), False
                return course, False
        return self.create_course(full_name, short_name, category_id), True

    def duplicate_course(
        self, course_id: int, full_name: str, short_name: str, category_id: int
    ) -> Any:
        return self.call(
            "core_course_duplicate_course",
            courseid=course_id,
            fullname=full_name,
            shortname=short_name,
            categoryid=category_id,
        )

    def format_update(
        self,
        course_id: int,
        action: str,
        ids: list[int] | None = None,
        **kwargs: Any,
    ) -> Any:
        params: dict[str, Any] = {"courseid": course_id, "action": action}
        if ids is not None:
            params["ids"] = ids
        params.update(kwargs)
        return self.call("core_courseformat_update_course", **params)

    def create_module(
        self,
        course_id: int,
        mod_name: str,
        section_num: int,
        **kwargs: Any,
    ) -> Any:
        return self.call(
            "core_courseformat_create_module",
            courseid=course_id,
            modname=mod_name,
            sectionnum=section_num,
            **kwargs,
        )

    def add_module_via_form(
        self,
        course_id: int,
        section_num: int,
        mod_name: str,
        name: str,
        intro: str = "",
        file_path: str | None = None,
    ) -> Any:
        """POST modedit.php. Needs a cookie session; token profiles raise MoodleError."""
        from moodle_cli._utils import require_session
        from moodle_cli.services.file import FileService

        session = require_session(self.client)
        session._ensure()
        draft = 0
        if file_path:
            uploaded = FileService(self.client).upload(file_path)
            if isinstance(uploaded, list) and uploaded:
                draft = int(uploaded[0].get("itemid") or 0)
            elif isinstance(uploaded, dict):
                draft = int(uploaded.get("itemid") or 0)
        url = f"{session.base_url}/course/modedit.php"
        data: dict[str, Any] = {
            "add": mod_name,
            "course": course_id,
            "section": section_num,
            "sesskey": session.sesskey,
            "modulename": mod_name,
            "name": name,
            "introeditor[text]": intro,
            "introeditor[format]": 1,
            "visible": 1,
            "_qf__mod_{modname}_mod_form": 1,
            "submitbutton": "Save and return to course",
        }
        if draft:
            data["files_filemanager"] = draft
            data["packagefile"] = draft
        resp = session.session.post(url, data=data, allow_redirects=True)
        resp.raise_for_status()
        return {"ok": True, "url": str(getattr(resp, "url", url))}

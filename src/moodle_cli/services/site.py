"""Site information service."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from moodle_cli.services.base import BaseService, MoodleModel


class SiteInfo(MoodleModel):
    site_name: Annotated[str, Field(validation_alias="sitename")]
    site_url: Annotated[str, Field(validation_alias="siteurl")]
    username: str
    full_name: Annotated[str, Field(validation_alias="fullname")]
    user_id: Annotated[int, Field(validation_alias="userid")]
    lang: str
    release: str
    version: str
    functions: list[dict[str, Any]] = []


class SiteFunction(MoodleModel):
    name: str
    version: str = ""


class SiteService(BaseService):
    def get_site_info(self) -> SiteInfo:
        data = self.call("core_webservice_get_site_info")
        return SiteInfo.model_validate(data)

    def get_functions(self) -> list[SiteFunction]:
        info = self.call("core_webservice_get_site_info")
        return [SiteFunction.model_validate(f) for f in info.get("functions", [])]

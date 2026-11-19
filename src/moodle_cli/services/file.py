"""File service."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from curl_cffi import CurlMime
from pydantic import Field

from moodle_cli.client.pages import filename
from moodle_cli.services.base import BaseService, MoodleModel


class MoodleFile(MoodleModel):
    file_name: Annotated[str, Field(validation_alias="filename")] = ""
    file_path: Annotated[str, Field(validation_alias="filepath")] = ""
    file_size: Annotated[int, Field(validation_alias="filesize")] = 0
    file_url: Annotated[str, Field(validation_alias="fileurl")] = ""
    time_created: Annotated[int, Field(validation_alias="timecreated")] = 0
    time_modified: Annotated[int, Field(validation_alias="timemodified")] = 0
    mime_type: Annotated[str, Field(validation_alias="mimetype")] = ""


class FileService(BaseService):
    def list_files(
        self,
        context_id: int,
        component: str = "user",
        file_area: str = "private",
        item_id: int = 0,
        file_path: str = "/",
    ) -> list[MoodleFile]:
        data = self.call(
            "core_files_get_files",
            contextid=context_id,
            component=component,
            filearea=file_area,
            itemid=item_id,
            filepath=file_path,
        )
        return [MoodleFile.model_validate(f) for f in data.get("files", [])]

    def upload(
        self,
        file_path: str,
        component: str = "user",
        file_area: str = "draft",
        item_id: int = 0,
    ) -> dict[str, Any]:
        """Upload a file to Moodle's draft area.

        Note: This uses a separate upload endpoint, not the REST API.
        """
        url = f"{self.client.base_url}/webservice/upload.php"
        mime = CurlMime()
        try:
            mime.addpart(name="token", data=self.client.token.encode())
            mime.addpart(name="component", data=component.encode())
            mime.addpart(name="filearea", data=file_area.encode())
            mime.addpart(name="itemid", data=str(item_id).encode())
            mime.addpart(name="file_1", local_path=file_path)
            resp = self.client.session.post(url, multipart=mime, timeout=60.0)
        finally:
            mime.close()
        resp.raise_for_status()
        return resp.json()

    def download(self, url: str, dest: str | None = None) -> dict[str, Any]:
        """Save a Moodle file URL using the current token or browser session."""
        fetch = url
        token = getattr(self.client, "token", "") or ""
        if token and "/pluginfile.php/" in url and "token=" not in url:
            fetch = f"{url}{'&' if '?' in url else '?'}token={token}"
        resp = self.client.session.get(fetch, allow_redirects=True, timeout=600.0)
        resp.raise_for_status()
        name = filename(str(resp.url), str(resp.headers.get("content-disposition") or ""))
        target = Path(dest) if dest else Path(name)
        if dest and Path(dest).is_dir():
            target = Path(dest) / name
        target.write_bytes(resp.content)
        return {"path": str(target), "filename": name, "size": len(resp.content)}

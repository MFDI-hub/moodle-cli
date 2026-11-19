"""Save course pages, tables, and links as md / html / txt (not pluginfile downloads)."""

from __future__ import annotations

import html
from pathlib import Path
from typing import TYPE_CHECKING, Any

from moodle_cli._utils import file_save_name, safe_name

if TYPE_CHECKING:
    from moodle_cli.api.models import Activity, Course, Section

PAGE_FORMATS = ("md", "html", "txt")

__all__ = ["PAGE_FORMATS", "file_save_name", "render_course", "write_pages"]


def write_pages(course: Course, dest: str | Path, fmt: str, *, deep: bool = False) -> Path:
    """Write ``course.{fmt}`` plus one file per section under ``pages/``."""
    fmt = _check(fmt)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    ext = f".{fmt}"
    title = course.full_name or course.short_name
    (dest / f"course{ext}").write_text(
        _document(title, render_course(course, fmt, deep=deep), fmt),
        encoding="utf-8",
    )
    folder = dest / "pages"
    folder.mkdir(exist_ok=True)
    for index, section in enumerate(course.sections):
        name = f"{index:02d}-{safe_name(section.name or 'section')}{ext}"
        heading = section.name or f"Section {index}"
        (folder / name).write_text(
            _document(heading, render_section(section, fmt, deep=deep, level=1), fmt),
            encoding="utf-8",
        )
    return dest


def render_course(course: Course, fmt: str, *, deep: bool = False) -> str:
    fmt = _check(fmt)
    parts = [_heading(course.full_name or course.short_name, 1, fmt)]
    if course.summary:
        parts.append(_paragraphs(course.summary, fmt))
    for section in course.sections:
        parts.append(render_section(section, fmt, deep=deep, level=2))
    return _join(parts, fmt)


def render_section(
    section: Section,
    fmt: str,
    *,
    deep: bool = False,
    level: int = 1,
) -> str:
    fmt = _check(fmt)
    parts = [_heading(section.name or "Section", level, fmt)]
    if section.summary:
        parts.append(_paragraphs(section.summary, fmt))
    if section.table:
        parts.append(_table(section.table, fmt))
    for activity in section.activities:
        parts.append(_activity(activity, fmt, deep=deep, level=level + 1))
    return _join(parts, fmt)


def _check(fmt: str) -> str:
    kind = (fmt or "").lower().lstrip(".")
    if kind not in PAGE_FORMATS:
        raise ValueError(f"pages format must be one of {PAGE_FORMATS}, got {fmt!r}")
    return kind


def _document(title: str, body: str, fmt: str) -> str:
    if fmt != "html":
        return body if body.endswith("\n") else body + "\n"
    return (
        '<!DOCTYPE html>\n<html lang="en"><head>'
        f'<meta charset="utf-8"><title>{html.escape(title)}</title></head>\n'
        f"<body>\n{body}\n</body></html>\n"
    )


def _join(parts: list[str], fmt: str) -> str:
    gap = "\n" if fmt == "html" else "\n\n"
    return gap.join(part for part in parts if part).strip() + "\n"


def _heading(text: str, level: int, fmt: str) -> str:
    text = (text or "").strip() or "Untitled"
    if fmt == "md":
        return f"{'#' * min(level, 6)} {text}"
    if fmt == "html":
        tag = f"h{min(max(level, 1), 6)}"
        return f"<{tag}>{html.escape(text)}</{tag}>"
    return text.upper() if level <= 2 else text


def _paragraphs(text: str, fmt: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if fmt == "md":
        return text
    if fmt == "html":
        blocks = [
            f"<p>{html.escape(block).replace(chr(10), '<br>')}</p>" for block in text.split("\n\n")
        ]
        return "\n".join(blocks)
    return text


def _link(name: str, url: str, fmt: str) -> str:
    name = name or url
    if not url:
        return name
    if fmt == "md":
        return f"[{_md_escape(name)}]({url})"
    if fmt == "html":
        return f'<a href="{html.escape(url, quote=True)}">{html.escape(name)}</a>'
    return f"{name} ({url})"


def _md_escape(text: str) -> str:
    return text.replace("[", "\\[").replace("]", "\\]").replace("\n", " ")


def _table(rows: list[dict[str, Any]], fmt: str) -> str:
    if not rows:
        return ""
    keys = list(rows[0].keys())
    if fmt == "md":
        header = "| " + " | ".join(_md_escape(key) for key in keys) + " |"
        rule = "| " + " | ".join("---" for _ in keys) + " |"
        body = ["| " + " | ".join(_cell(row.get(key), "md") for key in keys) + " |" for row in rows]
        return "\n".join([header, rule, *body])
    if fmt == "html":
        head = "".join(f"<th>{html.escape(key)}</th>" for key in keys)
        body = []
        for row in rows:
            cells = "".join(f"<td>{_cell(row.get(key), 'html')}</td>" for key in keys)
            body.append(f"<tr>{cells}</tr>")
        return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"
    lines = ["\t".join(keys)]
    for row in rows:
        lines.append("\t".join(_cell(row.get(key), "txt") for key in keys))
    return "\n".join(lines)


def _cell(value: Any, fmt: str) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        bits = [_item(item, fmt) for item in value]
        sep = ", " if fmt != "html" else "<br>"
        return sep.join(bit for bit in bits if bit)
    if isinstance(value, dict):
        return _item(value, fmt)
    text = str(value).replace("\n", " ")
    if fmt == "md":
        return _md_escape(text).replace("|", "\\|")
    if fmt == "html":
        return html.escape(text)
    return text


def _item(item: Any, fmt: str) -> str:
    if isinstance(item, dict):
        name = str(item.get("name") or item.get("filename") or item.get("url") or "")
        url = str(item.get("url") or "")
        if url:
            return _link(name, url, fmt)
        return _cell(name, fmt) if name else ""
    return _cell(item, fmt)


def _activity(activity: Activity, fmt: str, *, deep: bool, level: int) -> str:
    title = activity.name or activity.mod_name
    parts = [_heading(title, level, fmt)]
    kind = (activity.mod_name or "").strip()
    if kind:
        parts.append(_muted(kind, fmt))
    if activity.text:
        parts.append(_paragraphs(activity.text, fmt))
    if activity.table:
        parts.append(_table(activity.table, fmt))
    target = activity.target or (
        activity.url if kind.lower() in {"url", "resource", "lti", "link"} else ""
    )
    if target and not any(f.url == target for f in activity.files):
        parts.append(_link(activity.name or "Open", target, fmt))
    for ref in activity.files:
        parts.append(_bullet(_link(ref.name, ref.url, fmt), fmt))
    if deep:
        extra = activity.extra
        if extra:
            parts.append(_extra(extra, fmt))
    return _join(parts, fmt)


def _muted(text: str, fmt: str) -> str:
    if fmt == "md":
        return f"*{text}*"
    if fmt == "html":
        return f"<p><em>{html.escape(text)}</em></p>"
    return f"({text})"


def _bullet(text: str, fmt: str) -> str:
    if fmt == "md":
        return f"- {text}"
    if fmt == "html":
        return f"<p>{text}</p>"
    return f"- {text}"


def _extra(extra: Any, fmt: str) -> str:
    if extra is None:
        return ""
    if isinstance(extra, list):
        if not extra:
            return ""
        if all(isinstance(row, dict) for row in extra):
            keys = list(extra[0].keys())
            if keys:
                return _table(extra, fmt)
        return "\n".join(_bullet(str(row), fmt) for row in extra)
    if isinstance(extra, dict):
        return _paragraphs(
            "\n".join(
                f"{key}: {value}" for key, value in extra.items() if value not in (None, "", [])
            ),
            fmt,
        )
    return _paragraphs(str(extra), fmt)

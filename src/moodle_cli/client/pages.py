"""HTML readers for Moodle pages when AJAX web-service functions are not exposed.

Each parser takes page HTML and returns the dict shape the matching service already
unpacks from a web-service call. Fetching stays in the session client.
"""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlsplit, urlunsplit

_NAV_HREFS = ("/course/view.php", "/course/section.php", "/login/", "/my/")
_TIME_TAG = re.compile(r'(?is)<time\b[^>]*\bdatetime="([^"]+)"')
_HIDDEN = re.compile(r'(?is)<input\b[^>]*\btype="hidden"[^>]*>')
_ATTR = re.compile(r"""(?is)\b(\w+)\s*=\s*["']([^"']*)["']""")
_LINK = re.compile(r'(?is)<a\b[^>]*\bhref="([^"]+)"[^>]*>([\s\S]*?)</a>')
_USER_LINK = re.compile(r"(?i)/user/view\.php\?id=(\d+)")
_DISCUSS = re.compile(r"(?i)/mod/forum/discuss\.php\?d=(\d+)")
_ATTEMPT = re.compile(r"(?i)/mod/quiz/review\.php\?attempt=(\d+)")
_PLUGINFILE = re.compile(r"(?i)/pluginfile\.php/")
_ROW = re.compile(r"(?is)<tr\b[^>]*>([\s\S]*?)</tr>")
_CELL = re.compile(r"(?is)<t[dh]\b[^>]*>([\s\S]*?)</t[dh]>")
_OPTION = re.compile(r'(?is)<option\b[^>]*\bvalue="(\d+)"[^>]*>([\s\S]*?)</option>')
_WEAK_LINK = frozenset({"pdf", "link", "here", "click", "doc", "file", "download", "url"})
_TD = re.compile(r"(?is)<(t[dh])\b([^>]*)>([\s\S]*?)</\1>")
_TABLE = re.compile(r"(?is)<table\b[^>]*>([\s\S]*?)</table>")
_ROWSPAN = re.compile(r"(?i)rowspan\s*=\s*['\"]?(\d+)")
_COLSPAN = re.compile(r"(?i)colspan\s*=\s*['\"]?(\d+)")


def section_summary(
    page_html: str, base: str = ""
) -> tuple[str, list[dict[str, str]], list[dict[str, Any]]]:
    """Prose, named links, and table rows from a section page's summary."""
    fragment = class_inner(page_html, "summarytext")
    if not fragment:
        return "", [], []
    table_rows, table_links = parse_html_tables(fragment, base)
    stripped = _TABLE.sub("\n", fragment)
    prose = html_text(stripped)
    seen = {link["url"] for link in table_links}
    extra: list[dict[str, str]] = []
    for link in content_links(stripped, base):
        if link["url"] in seen:
            continue
        extra.append(_context_link(link, stripped))
        seen.add(link["url"])
    return prose, table_links + extra, table_rows


def parse_html_tables(
    fragment: str, base: str = ""
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Turn HTML tables into row dicts and give each file a row-based name."""
    rows: list[dict[str, Any]] = []
    links: list[dict[str, str]] = []
    for table_html in _TABLE.findall(fragment):
        grid = _table_grid(table_html)
        if not grid:
            continue
        if _looks_like_header(grid[0]):
            headers = [_header_key(cell, index) for index, cell in enumerate(grid[0])]
            body = grid[1:]
        else:
            headers = [f"col{index + 1}" for index in range(len(grid[0]))]
            body = grid
        for raw in body:
            row: dict[str, Any] = {}
            topic = ""
            for index, cell in enumerate(raw):
                key = headers[index] if index < len(headers) else f"col{index + 1}"
                text = html_text(cell)
                cell_links = content_links(cell, base)
                if key.lower() == "topic":
                    topic = text
                if cell_links:
                    named = []
                    for link in cell_links:
                        label = _table_link_name(topic, key, link)
                        named.append({"name": label, "url": link["url"]})
                        links.append({"name": label, "url": link["url"]})
                    row[key] = named
                else:
                    row[key] = text
            if any(value not in ("", []) for value in row.values()):
                rows.append(row)
    return rows, links


def module_bodies(page_html: str) -> dict[int, str]:
    """Label and description text keyed by course-module id."""
    bodies: dict[int, str] = {}
    matches = list(re.finditer(r'(?is)\bid="module-(\d+)"', page_html))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(page_html)
        text = html_text(class_inner(page_html[match.end() : end], "activity-altcontent"))
        if text:
            bodies[int(match.group(1))] = text
    return bodies


def activity_document(page_html: str, base: str = "") -> dict[str, Any]:
    """Page text, folder files, or the external URL from an activity page."""
    main = id_inner(page_html, "region-main") or page_html
    result: dict[str, Any] = {}
    target = re.search(r'(?is)class="urlworkaround"[\s\S]*?\bhref="([^"]+)"', main)
    if target:
        result["target"] = clean_url(target.group(1), base)
    files = [
        link
        for link in content_links(main, base)
        if "/pluginfile.php/" in link["url"] and "/theme_" not in link["url"]
    ]
    if files:
        result["files"] = files
    box = class_inner(main, "generalbox")
    if box:
        text = html_text(box)
        if text and not text.lower().startswith("click on"):
            result["text"] = text
    return result


def instance_from_html(page_html: str, module: str, cmid: int) -> int:
    """Activity instance id from a view page; falls back to the course-module id."""
    names = (
        f"{module}id",
        "instanceid",
        "instance",
        "assignmentid",
        "assignid",
        "quizid",
        "forum",
        "f",
        "id",
    )
    for tag in _HIDDEN.findall(page_html):
        attrs = dict(_ATTR.findall(tag))
        name = attrs.get("name", "")
        value = attrs.get("value", "")
        if name not in names or not value.isdigit():
            continue
        found = int(value)
        if name == "id" or not found:
            continue
        return found
    patterns = [
        r'"instanceid"\s*:\s*(\d+)',
        r'"instance"\s*:\s*(\d+)',
        r'data-instanceid="(\d+)"',
        rf"/mod/{re.escape(module)}/view\.php\?f=(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, page_html, re.I)
        if match:
            found = int(match.group(1))
            if found and found != cmid:
                return found
    return cmid


def parse_grade_report(page_html: str) -> list[dict[str, Any]]:
    """Grade items from the user grade report table."""
    items: list[dict[str, Any]] = []
    for row in _ROW.findall(page_html):
        name = html_text(_class_cell(row, "column-itemname") or "")
        grade = html_text(_class_cell(row, "column-grade") or "")
        span = html_text(_class_cell(row, "column-range") or "")
        feedback = html_text(_class_cell(row, "column-feedback") or "")
        if not name:
            continue
        if name.lower() in {"grade item", "item name"}:
            continue
        low, high = _range(span)
        items.append(
            {
                "itemname": name,
                "grade": grade,
                "grademin": low,
                "grademax": high,
                "feedback": feedback,
            }
        )
    return items


def parse_assign_view(page_html: str, cmid: int, course_id: int = 0) -> dict[str, Any]:
    """Assignment metadata and the current user's submission status."""
    main = id_inner(page_html, "region-main") or page_html
    name = _heading(page_html)
    due = _first_time(main)
    status = _submission_status(main)
    grade = _assign_grade(main)
    files = [
        link
        for link in content_links(main, "")
        if _PLUGINFILE.search(link["url"]) and "/theme_" not in link["url"]
    ]
    instance = instance_from_html(page_html, "assign", cmid)
    return {
        "id": instance,
        "cmid": cmid,
        "course": course_id,
        "name": name,
        "duedate": due,
        "grade": _float(grade) if grade else 0,
        "intro": html_text(class_inner(main, "activity-description") or ""),
        "status": status,
        "gradevalue": grade,
        "files": files,
        "instance": instance,
    }


def parse_forum_discussions(page_html: str, forum_id: int = 0) -> list[dict[str, Any]]:
    """Discussion rows from a forum view page."""
    discussions: list[dict[str, Any]] = []
    seen: set[int] = set()
    for row in _ROW.findall(page_html):
        disc = None
        subject = ""
        for href, inner in _LINK.findall(row):
            match = _DISCUSS.search(html.unescape(href))
            if match:
                disc = int(match.group(1))
                subject = html_text(inner)
                break
        if disc is None or disc in seen:
            continue
        seen.add(disc)
        cells = [html_text(cell) for cell in _CELL.findall(row)]
        user_id, user_name = _user_from(row)
        replies = _int_in(cells, skip={disc})
        discussions.append(
            {
                "id": disc,
                "discussion": disc,
                "forum": forum_id,
                "name": subject,
                "subject": subject,
                "message": "",
                "userid": user_id,
                "userfullname": user_name,
                "timemodified": _first_time(row),
                "created": _first_time(row),
                "numreplies": replies,
                "numunread": 0,
                "usermodified": 0,
                "usermodifiedfullname": cells[-1] if len(cells) > 2 else "",
                "pinned": False,
                "locked": False,
            }
        )
    if discussions:
        return discussions
    for href, inner in _LINK.findall(page_html):
        match = _DISCUSS.search(html.unescape(href))
        if not match:
            continue
        disc = int(match.group(1))
        if disc in seen:
            continue
        seen.add(disc)
        subject = html_text(inner)
        discussions.append(
            {
                "id": disc,
                "discussion": disc,
                "forum": forum_id,
                "name": subject,
                "subject": subject,
                "message": "",
                "userid": 0,
                "userfullname": "",
                "timemodified": 0,
                "created": 0,
                "numreplies": 0,
                "numunread": 0,
                "usermodified": 0,
                "usermodifiedfullname": "",
                "pinned": False,
                "locked": False,
            }
        )
    return discussions


def parse_forum_posts(page_html: str, discussion_id: int = 0) -> list[dict[str, Any]]:
    """Posts in a discussion thread."""
    posts: list[dict[str, Any]] = []
    for match in re.finditer(
        r"(?is)<(?:article|div)\b([^>]*\b(?:forumpost|forum-post-container)[^>]*)>([\s\S]*?)</(?:article|div)>",
        page_html,
    ):
        attrs, body = match.group(1), match.group(2)
        post_id = _id_attr(attrs) or _id_attr(body)
        if not post_id:
            continue
        user_id, user_name = _user_from(body)
        subject = html_text(class_inner(body, "subject") or class_inner(body, "post-subject") or "")
        if not subject:
            heading = re.search(r"(?is)<h[1-6][^>]*>([\s\S]*?)</h[1-6]>", body)
            subject = html_text(heading.group(1)) if heading else ""
        message = html_text(
            class_inner(body, "post-message")
            or class_inner(body, "posting")
            or class_inner(body, "post-content")
            or body
        )
        posts.append(
            {
                "id": post_id,
                "discussionid": discussion_id,
                "parentid": None,
                "subject": subject,
                "message": message,
                "timecreated": _first_time(body),
                "author": {"id": user_id, "fullname": user_name},
            }
        )
    return posts


def parse_quiz_view(page_html: str, quiz_id: int = 0, course_id: int = 0) -> dict[str, Any]:
    """Quiz summary, attempts, and best grade from the quiz view page."""
    attempts: list[dict[str, Any]] = []
    for row in _ROW.findall(page_html):
        attempt_id = 0
        for href, _inner in _LINK.findall(row):
            found = _ATTEMPT.search(html.unescape(href))
            if found:
                attempt_id = int(found.group(1))
                break
        cells = [html_text(cell) for cell in _CELL.findall(row)]
        if not attempt_id and not any(
            cell.lower() in {"finished", "in progress"} for cell in cells
        ):
            continue
        state = next(
            (
                cell.lower()
                for cell in cells
                if cell.lower() in {"finished", "in progress", "overdue"}
            ),
            "finished" if attempt_id else "",
        )
        grade = _quiz_grade(cells)
        number = _first_int(cells)
        attempts.append(
            {
                "id": attempt_id or number,
                "quiz": quiz_id,
                "userid": 0,
                "attempt": number or len(attempts) + 1,
                "state": state.replace(" ", "") or "finished",
                "grade": grade,
                "timestart": _first_time(row),
                "timefinish": _first_time(row),
            }
        )
    best = None
    has = False
    match = re.search(r"(?i)(?:highest|best)\s+grade[^0-9]*([0-9]+(?:\.[0-9]+)?)", page_html)
    if match:
        best = float(match.group(1))
        has = True
    elif attempts:
        nums = [a["grade"] for a in attempts if isinstance(a.get("grade"), (int, float))]
        if nums:
            best = max(nums)
            has = True
    return {
        "name": _heading(page_html),
        "id": quiz_id,
        "course": course_id,
        "attempts": attempts,
        "hasgrade": has,
        "grade": best,
    }


def parse_quiz_review(page_html: str, attempt_id: int = 0) -> dict[str, Any]:
    """Question text and marks from a finished attempt review."""
    questions: list[dict[str, Any]] = []
    blocks = re.findall(
        r'(?is)<div\b[^>]*\bclass="[^"]*\bque\b[^"]*"[^>]*>([\s\S]*?)(?=<div\b[^>]*class="[^"]*\bque\b|$)',
        page_html,
    )
    for index, block in enumerate(blocks, start=1):
        text = html_text(class_inner(block, "qtext") or block)
        mark = _first_float([html_text(class_inner(block, "grade") or "")])
        state = html_text(class_inner(block, "state") or "")
        questions.append(
            {
                "slot": index,
                "html": text,
                "mark": mark if mark is not None else "",
                "status": state,
            }
        )
    grade = None
    match = re.search(r"(?i)grade[^0-9]*([0-9]+(?:\.[0-9]+)?)", html_text(page_html)[:800])
    if match:
        grade = float(match.group(1))
    return {"attemptid": attempt_id, "grade": grade, "questions": questions}


def parse_participants(page_html: str, course_id: int = 0) -> list[dict[str, Any]]:
    """Enrolled users from the participants page."""
    users: list[dict[str, Any]] = []
    seen: set[int] = set()
    for row in _ROW.findall(page_html):
        user_id, fullname = _user_from(row)
        if not user_id or user_id in seen:
            continue
        seen.add(user_id)
        cells = [html_text(cell) for cell in _CELL.findall(row)]
        email = next((cell for cell in cells if "@" in cell), "")
        role = next(
            (
                cell
                for cell in cells
                if cell.lower() in {"student", "teacher", "editingteacher", "manager", "guest"}
                or "teacher" in cell.lower()
                or "student" in cell.lower()
            ),
            "",
        )
        users.append(
            {
                "id": user_id,
                "username": "",
                "fullname": fullname,
                "firstname": fullname.split(" ", 1)[0] if fullname else "",
                "lastname": fullname.split(" ", 1)[-1] if " " in fullname else "",
                "email": email,
                "roles": [{"shortname": role.lower().replace(" ", "")}] if role else [],
                "lastaccess": _first_time(row) or None,
                "lastcourseaccess": _first_time(row) or None,
                "groups": [],
                "courseid": course_id,
            }
        )
    if users:
        return users
    for href, inner in _LINK.findall(page_html):
        match = _USER_LINK.search(html.unescape(href))
        if not match:
            continue
        user_id = int(match.group(1))
        if user_id in seen:
            continue
        seen.add(user_id)
        fullname = html_text(inner)
        users.append(
            {
                "id": user_id,
                "username": "",
                "fullname": fullname,
                "firstname": fullname.split(" ", 1)[0] if fullname else "",
                "lastname": fullname.split(" ", 1)[-1] if " " in fullname else "",
                "email": "",
                "roles": [],
                "lastaccess": None,
                "lastcourseaccess": None,
                "groups": [],
                "courseid": course_id,
            }
        )
    return users


def parse_groups(page_html: str, course_id: int = 0) -> list[dict[str, Any]]:
    """Course groups from the groups index."""
    groups: list[dict[str, Any]] = []
    fragment = id_inner(page_html, "groups") or page_html
    for value, label in _OPTION.findall(fragment):
        gid = int(value)
        if not gid:
            continue
        name = re.sub(r"\s*\(\d+\)\s*$", "", html_text(label))
        groups.append(
            {
                "id": gid,
                "courseid": course_id,
                "name": name,
                "description": "",
                "descriptionformat": 1,
            }
        )
    if groups:
        return groups
    for href, inner in _LINK.findall(page_html):
        match = re.search(r"(?i)/group/overview\.php\?id=\d+&group=(\d+)", html.unescape(href))
        if not match:
            continue
        groups.append(
            {
                "id": int(match.group(1)),
                "courseid": course_id,
                "name": html_text(inner),
                "description": "",
                "descriptionformat": 1,
            }
        )
    return groups


def parse_groupings(page_html: str, course_id: int = 0) -> list[dict[str, Any]]:
    """Groupings from the groupings tab."""
    groupings: list[dict[str, Any]] = []
    fragment = id_inner(page_html, "groupings") or page_html
    for value, label in _OPTION.findall(fragment):
        gid = int(value)
        if gid:
            groupings.append(
                {"id": gid, "courseid": course_id, "name": html_text(label), "description": ""}
            )
    for href, inner in _LINK.findall(page_html):
        match = re.search(r"(?i)groupingid=(\d+)", html.unescape(href))
        if match:
            groupings.append(
                {
                    "id": int(match.group(1)),
                    "courseid": course_id,
                    "name": html_text(inner),
                    "description": "",
                }
            )
    return groupings


def parse_categories(page_html: str) -> list[dict[str, Any]]:
    """Course categories from the course index."""
    categories: list[dict[str, Any]] = []
    seen: set[int] = set()
    for href, inner in _LINK.findall(page_html):
        match = re.search(r"(?i)categoryid=(\d+)", html.unescape(href))
        if not match:
            continue
        cid = int(match.group(1))
        if cid in seen:
            continue
        seen.add(cid)
        categories.append(
            {
                "id": cid,
                "name": html_text(inner),
                "parent": 0,
                "coursecount": 0,
                "depth": 0,
                "visible": 1,
            }
        )
    return categories


def parse_completion(page_html: str) -> list[dict[str, Any]]:
    """Per-activity completion rows from the progress report."""
    statuses: list[dict[str, Any]] = []
    for href, inner in _LINK.findall(page_html):
        match = re.search(r"(?i)/mod/(\w+)/view\.php\?id=(\d+)", html.unescape(href))
        if not match:
            continue
        name = html_text(inner)
        completed = bool(re.search(r"(?i)\b(completed|yes|done)\b", name))
        statuses.append(
            {
                "cmid": int(match.group(2)),
                "modname": match.group(1),
                "instance": 0,
                "state": 1 if completed else 0,
                "timecompleted": 0,
                "tracking": 1,
                "name": name,
            }
        )
    for row in _ROW.findall(page_html):
        cmid = 0
        modname = ""
        for href, _inner in _LINK.findall(row):
            match = re.search(r"(?i)/mod/(\w+)/view\.php\?id=(\d+)", html.unescape(href))
            if match:
                modname, cmid = match.group(1), int(match.group(2))
                break
        if not cmid:
            continue
        text = html_text(row).lower()
        completed = "completed" in text or "yes" in text
        existing = next((item for item in statuses if item["cmid"] == cmid), None)
        if existing:
            existing["state"] = 1 if completed else existing["state"]
        else:
            statuses.append(
                {
                    "cmid": cmid,
                    "modname": modname,
                    "instance": 0,
                    "state": 1 if completed else 0,
                    "timecompleted": 0,
                    "tracking": 1,
                }
            )
    return statuses


def parse_messages(page_html: str) -> list[dict[str, Any]]:
    """Messages from the messaging index."""
    messages: list[dict[str, Any]] = []
    for match in re.finditer(
        r'(?is)data-message-id="(\d+)"[^>]*>([\s\S]*?)</(?:div|li)>',
        page_html,
    ):
        body = match.group(2)
        user_id, _name = _user_from(body)
        messages.append(
            {
                "id": int(match.group(1)),
                "useridfrom": user_id,
                "useridto": 0,
                "text": html_text(body),
                "timecreated": _first_time(body),
            }
        )
    return messages


def parse_conversations(page_html: str) -> list[dict[str, Any]]:
    """Conversation list from the messaging index."""
    conversations: list[dict[str, Any]] = []
    for match in re.finditer(
        r'(?is)data-conversation-id="(\d+)"[^>]*>([\s\S]*?)</(?:div|a|li)>',
        page_html,
    ):
        body = match.group(2)
        conversations.append(
            {
                "id": int(match.group(1)),
                "name": html_text(body) or None,
                "type": 1,
                "membercount": 0,
                "unreadcount": None,
            }
        )
    return conversations


def parse_badges(page_html: str) -> list[dict[str, Any]]:
    """Awarded badges from the my-badges page."""
    badges: list[dict[str, Any]] = []
    for match in re.finditer(
        r'(?is)<(?:div|li)\b[^>]*\bclass="[^"]*\bbadge\b[^"]*"[^>]*>([\s\S]*?)</(?:div|li)>',
        page_html,
    ):
        body = match.group(1)
        name = html_text(class_inner(body, "badge-name") or _heading_fragment(body) or "")
        if not name:
            continue
        badges.append(
            {
                "id": _id_attr(body) or len(badges) + 1,
                "name": name,
                "description": html_text(class_inner(body, "badge-description") or ""),
                "courseid": None,
                "dateissued": _first_time(body),
                "issuername": "",
            }
        )
    if badges:
        return badges
    for href, inner in _LINK.findall(page_html):
        if "/badges/" not in html.unescape(href):
            continue
        name = html_text(inner)
        if name:
            badges.append(
                {
                    "id": len(badges) + 1,
                    "name": name,
                    "description": "",
                    "courseid": None,
                    "dateissued": 0,
                    "issuername": "",
                }
            )
    return badges


def parse_files(page_html: str, base: str = "") -> list[dict[str, Any]]:
    """Private-files listing."""
    files: list[dict[str, Any]] = []
    for link in content_links(page_html, base):
        if "/pluginfile.php/" not in link["url"] or "/theme_" in link["url"]:
            continue
        files.append(
            {
                "filename": link["name"],
                "filepath": "/",
                "filesize": 0,
                "fileurl": link["url"],
                "timecreated": 0,
                "timemodified": 0,
                "mimetype": "",
            }
        )
    return files


def parse_named_items(page_html: str, id_pattern: str) -> list[dict[str, Any]]:
    """Generic id + name rows from links matching ``id_pattern`` (with one capture)."""
    items: list[dict[str, Any]] = []
    seen: set[int] = set()
    regex = re.compile(id_pattern, re.I)
    for href, inner in _LINK.findall(page_html):
        match = regex.search(html.unescape(href))
        if not match:
            continue
        item_id = int(match.group(1))
        if item_id in seen:
            continue
        seen.add(item_id)
        items.append({"id": item_id, "name": html_text(inner), "title": html_text(inner)})
    return items


def parse_glossary(page_html: str) -> list[dict[str, Any]]:
    """Glossary entries."""
    entries: list[dict[str, Any]] = []
    for match in re.finditer(
        r'(?is)<div\b[^>]*\bclass="[^"]*glossarypost[^"]*"[^>]*>([\s\S]*?)</div>',
        page_html,
    ):
        body = match.group(1)
        concept = html_text(class_inner(body, "concept") or _heading_fragment(body) or "")
        definition = html_text(class_inner(body, "definition") or body)
        if concept:
            entries.append({"id": len(entries) + 1, "concept": concept, "definition": definition})
    if entries:
        return entries
    for item in parse_named_items(page_html, r"[?&]eid=(\d+)"):
        entries.append({"id": item["id"], "concept": item["name"], "definition": ""})
    return entries


def parse_workshop(page_html: str) -> list[dict[str, Any]]:
    """Workshop submissions visible to the current user."""
    submissions: list[dict[str, Any]] = []
    for href, inner in _LINK.findall(page_html):
        match = re.search(r"(?i)[?&]sid=(\d+)|submissionid=(\d+)", html.unescape(href))
        if not match:
            continue
        sid = int(match.group(1) or match.group(2))
        submissions.append(
            {"id": sid, "title": html_text(inner), "authorid": _user_from(inner)[0] or 0}
        )
    return submissions


def parse_database(page_html: str) -> list[dict[str, Any]]:
    """Database activity entries."""
    entries: list[dict[str, Any]] = []
    for href, inner in _LINK.findall(page_html):
        match = re.search(r"(?i)[?&]rid=(\d+)", html.unescape(href))
        if not match:
            continue
        entries.append(
            {
                "id": int(match.group(1)),
                "userid": _user_from(inner)[0] or 0,
                "approved": 1,
                "name": html_text(inner),
            }
        )
    return entries


def parse_wiki_pages(page_html: str) -> list[dict[str, Any]]:
    """Wiki page index."""
    pages: list[dict[str, Any]] = []
    for href, inner in _LINK.findall(page_html):
        match = re.search(r"(?i)/mod/wiki/view\.php\?pageid=(\d+)", html.unescape(href))
        if not match:
            continue
        pages.append(
            {
                "id": int(match.group(1)),
                "title": html_text(inner),
                "timemodified": _first_time(inner),
            }
        )
    return pages


def parse_wiki_page(page_html: str, page_id: int = 0) -> dict[str, Any]:
    """A single wiki page body."""
    main = id_inner(page_html, "region-main") or page_html
    content = class_inner(main, "wiki_content") or class_inner(main, "generalbox") or main
    return {
        "id": page_id,
        "title": _heading(page_html),
        "cachedcontent": html_text(content),
    }


def parse_book_chapters(page_html: str, base: str = "") -> list[dict[str, Any]]:
    """Chapter links from a book view page."""
    chapters: list[dict[str, Any]] = []
    seen: set[str] = set()
    for href, inner in _LINK.findall(page_html):
        url = clean_url(href, base)
        if "chapterid=" not in url or url in seen:
            continue
        seen.add(url)
        query = dict(parse_qsl(urlsplit(url).query))
        name = html_text(inner) or f"Chapter {query.get('chapterid', len(chapters) + 1)}"
        chapters.append({"name": name, "url": url, "id": int(query.get("chapterid") or 0)})
    return chapters


def parse_lesson(page_html: str) -> list[dict[str, Any]]:
    """Lesson page list."""
    pages: list[dict[str, Any]] = []
    for href, inner in _LINK.findall(page_html):
        match = re.search(r"(?i)/mod/lesson/view\.php\?id=\d+&pageid=(\d+)", html.unescape(href))
        if not match:
            continue
        pages.append(
            {
                "page": {
                    "id": int(match.group(1)),
                    "title": html_text(inner),
                    "typestring": "",
                    "qtype": 0,
                }
            }
        )
    return pages


def parse_notes(page_html: str, course_id: int = 0) -> list[dict[str, Any]]:
    """Teacher notes on the course notes page."""
    notes: list[dict[str, Any]] = []
    for match in re.finditer(
        r'(?is)<(?:div|li)\b[^>]*\bclass="[^"]*note[^"]*"[^>]*>([\s\S]*?)</(?:div|li)>',
        page_html,
    ):
        body = match.group(1)
        user_id, _name = _user_from(body)
        notes.append(
            {
                "id": _id_attr(body) or len(notes) + 1,
                "userid": user_id,
                "courseid": course_id,
                "content": html_text(body),
            }
        )
    return notes


def parse_choice_results(page_html: str) -> list[dict[str, Any]]:
    """Choice option totals."""
    options: list[dict[str, Any]] = []
    for row in _ROW.findall(page_html):
        cells = [html_text(cell) for cell in _CELL.findall(row)]
        if len(cells) < 2:
            continue
        if cells[0].lower() in {"choice", "option", "response"}:
            continue
        options.append({"text": cells[0], "number": _first_int(cells[1:]) or cells[1]})
    return options


def parse_feedback_analysis(page_html: str) -> dict[str, Any]:
    """Feedback analysis text."""
    main = id_inner(page_html, "region-main") or page_html
    return {"items": [], "completedcount": 0, "text": html_text(main)}


def parse_cohorts(page_html: str) -> list[dict[str, Any]]:
    """Cohorts from the cohort index."""
    cohorts: list[dict[str, Any]] = []
    seen: set[int] = set()
    for href, inner in _LINK.findall(page_html):
        match = re.search(r"(?i)cohortid=(\d+)|/cohort/view\.php\?id=(\d+)", html.unescape(href))
        if not match:
            continue
        cid = int(match.group(1) or match.group(2))
        if cid in seen:
            continue
        seen.add(cid)
        cohorts.append(
            {
                "id": cid,
                "name": html_text(inner),
                "idnumber": "",
                "description": "",
                "visible": True,
            }
        )
    return cohorts


def parse_enrol_methods(page_html: str, course_id: int = 0) -> list[dict[str, Any]]:
    """Enrolment methods from the enrolment index."""
    methods: list[dict[str, Any]] = []
    for row in _ROW.findall(page_html):
        cells = [html_text(cell) for cell in _CELL.findall(row)]
        if len(cells) < 2:
            continue
        name = cells[0]
        if name.lower() in {"name", "enrolment method"}:
            continue
        methods.append(
            {
                "id": len(methods) + 1,
                "courseid": course_id,
                "type": name.lower().replace(" ", ""),
                "name": name,
                "status": cells[1] if len(cells) > 1 else "",
            }
        )
    return methods


def parse_activity_intro(page_html: str, module: str, cmid: int, course_id: int) -> dict[str, Any]:
    """Shared fields for a module listed by ``content list`` / ``*_by_courses``."""
    instance = instance_from_html(page_html, module, cmid)
    intro = html_text(
        class_inner(page_html, "activity-description") or class_inner(page_html, "intro") or ""
    )
    return {
        "id": instance,
        "course": course_id,
        "coursemodule": cmid,
        "name": _heading(page_html),
        "intro": intro,
        "visible": 1,
        "instance": instance,
    }


def text(value: object) -> str:
    return html.unescape(_strip_tags(str(value or "")))


def html_text(fragment: str) -> str:
    if not fragment:
        return ""
    fragment = re.sub(r"(?is)<script[\s\S]*?</script>", " ", fragment)
    fragment = re.sub(r"(?is)<style[\s\S]*?</style>", " ", fragment)
    fragment = re.sub(r"(?i)<br\s*/?>", "\n", fragment)
    fragment = re.sub(r"(?i)</(?:p|div|tr|li|h[1-6]|table|ul|ol|blockquote)>", "\n", fragment)
    fragment = re.sub(r"(?i)<t[dh]\b[^>]*>", " ", fragment)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    fragment = html.unescape(fragment).replace("\xa0", " ")
    lines: list[str] = []
    for raw in fragment.splitlines():
        line = re.sub(r"[ \t]+", " ", raw).strip()
        if line:
            lines.append(line)
        elif lines and lines[-1] != "":
            lines.append("")
    return "\n".join(lines).strip()


def _table_grid(table_html: str) -> list[list[str]]:
    occupy: dict[tuple[int, int], str] = {}
    grid: list[list[str]] = []
    for row_index, row_html in enumerate(_ROW.findall(table_html)):
        cells = []
        for match in _TD.finditer(row_html):
            attrs, inner = match.group(2), match.group(3)
            rowspan = int(m.group(1)) if (m := _ROWSPAN.search(attrs)) else 1
            colspan = int(m.group(1)) if (m := _COLSPAN.search(attrs)) else 1
            cells.append((inner, max(rowspan, 1), max(colspan, 1)))
        line: list[str] = []
        column = 0
        cell_index = 0
        while cell_index < len(cells) or (row_index, column) in occupy:
            if (row_index, column) in occupy:
                line.append(occupy[(row_index, column)])
                column += 1
                continue
            if cell_index >= len(cells):
                break
            inner, rowspan, colspan = cells[cell_index]
            cell_index += 1
            for offset in range(colspan):
                line.append(inner if offset == 0 else "")
                for down in range(1, rowspan):
                    occupy[(row_index + down, column + offset)] = inner if offset == 0 else ""
            column += colspan
        grid.append(line)
    width = max((len(row) for row in grid), default=0)
    return [row + [""] * (width - len(row)) for row in grid]


def _looks_like_header(row: list[str]) -> bool:
    texts = [html_text(cell).lower() for cell in row]
    if not texts:
        return False
    return any(word in " ".join(texts) for word in ("week", "date", "topic", "slides"))


def _header_key(cell: str, index: int) -> str:
    name = html_text(cell) or f"col{index + 1}"
    return name.strip()


def _table_link_name(topic: str, column: str, link: dict[str, str]) -> str:
    raw = link.get("name") or ""
    if raw.lower() in _WEAK_LINK:
        raw = _name_from_url(link["url"]) or raw
    if topic and raw.lower() in _WEAK_LINK:
        return f"{topic} ({column})"
    if topic and raw:
        return f"{topic} — {raw}"
    return raw or column


def _name_from_url(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    if "sharepoint" in host:
        return ""
    leaf = unquote(urlsplit(url).path.rstrip("/").split("/")[-1])
    leaf = re.sub(r"\.(pdf|pptx?|zip|docx?)$", "", leaf, flags=re.I)
    leaf = leaf.replace("_", " ").replace("-", " ").strip()
    if not leaf or leaf.lower() in _WEAK_LINK | {"view", "index.html", "index"}:
        return ""
    return leaf


def _context_link(link: dict[str, str], fragment: str) -> dict[str, str]:
    name = link.get("name") or ""
    if name.lower() not in _WEAK_LINK:
        return link
    better = _name_from_url(link["url"])
    if better:
        return {"name": better, "url": link["url"]}
    idx = fragment.find(link["url"])
    if idx < 0:
        idx = fragment.find(html.escape(link["url"]))
    window = html_text(fragment[max(0, idx - 180) : idx]) if idx >= 0 else ""
    words = window.split()[-10:]
    context = " ".join(words).strip(" -:;,.")
    if context:
        return {"name": f"{context} ({name})", "url": link["url"]}
    return link


def content_links(fragment: str, base: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for href, inner in _LINK.findall(fragment):
        url = clean_url(href, base)
        if not url.startswith(("http://", "https://")) or any(part in url for part in _NAV_HREFS):
            continue
        if "/theme_" in url or url in seen:
            continue
        seen.add(url)
        links.append({"name": html_text(inner) or filename(url), "url": url})
    return links


def clean_url(url: str, base: str) -> str:
    url = html.unescape(url).strip()
    if base and not url.startswith(("http://", "https://", "javascript:", "mailto:", "#")):
        url = urljoin(base, url)
    parts = urlsplit(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key != "sesskey"
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def filename(url: str, disposition: str = "") -> str:
    if disposition:
        match = re.search(
            r"filename\*=UTF-8''([^;]+)|filename=\"([^\"]+)\"|filename=([^;]+)",
            disposition,
            re.IGNORECASE,
        )
        if match:
            return unquote((match.group(1) or match.group(2) or match.group(3) or "").strip())
    name = unquote(urlsplit(url).path.rstrip("/").split("/")[-1])
    return name or url


def is_html(resp: Any) -> bool:
    ctype = str(resp.headers.get("content-type") or "")
    if not ctype:
        return str(getattr(resp, "text", "")).lstrip().startswith("<")
    return "html" in ctype


def id_inner(page_html: str, element_id: str) -> str:
    match = re.search(
        rf'(?is)<(?:div|table|ul|ol|select)\b[^>]*\bid="{re.escape(element_id)}"[^>]*>', page_html
    )
    if not match:
        return ""
    return _balanced(page_html, match.end(), match.group(0).lstrip("<").split()[0].split(">")[0])


def class_inner(page_html: str, class_name: str) -> str:
    match = re.search(
        rf'(?is)<div\b[^>]*\bclass="[^"]*\b{re.escape(class_name)}\b[^"]*"[^>]*>',
        page_html,
    )
    if not match:
        return ""
    return _balanced_div(page_html, match.end())


def _balanced_div(page_html: str, start: int) -> str:
    return _balanced(page_html, start, "div")


def _balanced(page_html: str, start: int, tag: str) -> str:
    depth = 1
    for match in re.finditer(rf"(?is)</?{re.escape(tag)}\b[^>]*>", page_html[start:]):
        depth += -1 if match.group(0).lower().startswith("</") else 1
        if depth == 0:
            return page_html[start : start + match.start()]
    return page_html[start:]


def _strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip()


def _class_cell(row: str, class_name: str) -> str:
    match = re.search(
        rf'(?is)<t[dh]\b[^>]*\bclass="[^"]*\b{re.escape(class_name)}\b[^"]*"[^>]*>([\s\S]*?)</t[dh]>',
        row,
    )
    return match.group(1) if match else ""


def _heading(page_html: str) -> str:
    match = re.search(r"(?is)<h1\b[^>]*>([\s\S]*?)</h1>", page_html)
    if match:
        return html_text(match.group(1))
    return html_text(_heading_fragment(page_html) or "")


def _heading_fragment(fragment: str) -> str:
    match = re.search(r"(?is)<h[1-6]\b[^>]*>([\s\S]*?)</h[1-6]>", fragment)
    return match.group(1) if match else ""


def _first_time(fragment: str) -> int:
    match = _TIME_TAG.search(fragment)
    if match:
        return unix_time(match.group(1))
    return 0


def unix_time(value: str) -> int:
    value = html.unescape(value).strip()
    if value.isdigit():
        return int(value)
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return 0


def _range(span: str) -> tuple[float, float]:
    nums = re.findall(r"[0-9]+(?:\.[0-9]+)?", span.replace(",", ""))
    if len(nums) >= 2:
        return float(nums[0]), float(nums[1])
    if len(nums) == 1:
        return 0.0, float(nums[0])
    return 0.0, 0.0


def _submission_status(fragment: str) -> dict[str, str]:
    text_value = html_text(fragment).lower()
    if "submitted for grading" in text_value or "submitted" in text_value:
        status = "submitted"
    elif "draft" in text_value:
        status = "draft"
    elif "no submission" in text_value or "not submitted" in text_value:
        status = "new"
    else:
        status = "new"
    grading = "graded" if re.search(r"\bgraded\b", text_value) else "notgraded"
    return {"status": status, "gradingstatus": grading}


def _assign_grade(fragment: str) -> str:
    match = re.search(r"(?i)grade[:\s]+([0-9]+(?:\.[0-9]+)?)", html_text(fragment))
    return match.group(1) if match else ""


def _user_from(fragment: str) -> tuple[int, str]:
    for href, inner in _LINK.findall(fragment):
        match = _USER_LINK.search(html.unescape(href))
        if match:
            return int(match.group(1)), html_text(inner)
    return 0, ""


def _id_attr(fragment: str) -> int:
    match = re.search(r'\bid="(?:p|post-?)(\d+)"', fragment, re.I)
    if match:
        return int(match.group(1))
    match = re.search(r'\bid="(\d+)"', fragment)
    return int(match.group(1)) if match else 0


def _int_in(cells: list[str], skip: set[int] | None = None) -> int:
    skip = skip or set()
    for cell in cells:
        if cell.isdigit():
            value = int(cell)
            if value not in skip:
                return value
    return 0


def _first_int(cells: list[str]) -> int:
    for cell in cells:
        match = re.search(r"\d+", cell)
        if match:
            return int(match.group(0))
    return 0


def _first_float(cells: list[str]) -> float | None:
    return _quiz_grade(cells)


def _quiz_grade(cells: list[str]) -> float | None:
    decimals: list[float] = []
    ints: list[float] = []
    for cell in cells:
        match = re.search(r"[0-9]+(?:\.[0-9]+)?", cell.replace(",", ""))
        if not match:
            continue
        raw = match.group(0)
        value = float(raw)
        if "." in raw:
            decimals.append(value)
        else:
            ints.append(value)
    if decimals:
        return decimals[-1]
    if len(ints) > 1:
        return ints[-1]
    return None


def _float(value: str) -> float:
    match = re.search(r"[0-9]+(?:\.[0-9]+)?", value.replace(",", ""))
    return float(match.group(0)) if match else 0.0

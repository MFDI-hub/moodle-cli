"""Course commands."""

from __future__ import annotations

from pathlib import Path

import click

from moodle_cli._utils import parse_customfields
from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context, preview_call
from moodle_cli.output import console, render_json, render_table, status, trim
from moodle_cli.services.backup import BackupService
from moodle_cli.services.course import CourseService
from moodle_cli.services.notify import notify as send_notifications
from moodle_cli.services.sync import SyncStore, sync_course


@click.group()
def course() -> None:
    """Course management."""


def _print_categories(ctx: MoodleContext) -> None:
    cats = ctx.get_moodle().categories
    if ctx.json_output:
        render_json([c.to_dict() for c in cats])
    else:
        rows = [
            {"ID": c.id, "Name": c.name, "Parent": c.parent, "Courses": c.course_count}
            for c in cats
        ]
        render_table(rows, title=f"Categories ({len(rows)})")


@course.group(invoke_without_command=True)
@pass_context
@handle_errors
def categories(ctx: MoodleContext) -> None:
    """List and manage course categories."""
    if click.get_current_context().invoked_subcommand is None:
        _print_categories(ctx)


@categories.command("list")
@pass_context
@handle_errors
def categories_list(ctx: MoodleContext) -> None:
    """List course categories."""
    _print_categories(ctx)


@categories.command("create")
@click.option("--name", required=True)
@click.option("--parent", default=0, type=int)
@click.option("--description", default="")
@pass_context
@handle_errors
def categories_create(ctx: MoodleContext, name: str, parent: int, description: str) -> None:
    """Create a course category."""
    if preview_call(
        ctx,
        "core_course_create_categories",
        categories=[{"name": name, "parent": parent, "description": description}],
    ):
        return
    rows = CourseService(ctx.get_client()).create_categories(name, parent, description)
    if ctx.json_output:
        render_json(rows)
    else:
        console.print(f"[green]Created category '{name}'[/green]")


@categories.command("update")
@click.argument("category_id", type=int)
@click.option("--name", default=None)
@click.option("--parent", default=None, type=int)
@pass_context
@handle_errors
def categories_update(
    ctx: MoodleContext, category_id: int, name: str | None, parent: int | None
) -> None:
    """Update a course category."""
    kwargs: dict[str, object] = {}
    if name is not None:
        kwargs["name"] = name
    if parent is not None:
        kwargs["parent"] = parent
    if preview_call(
        ctx, "core_course_update_categories", categories=[{"id": category_id, **kwargs}]
    ):
        return
    CourseService(ctx.get_client()).update_categories(category_id, **kwargs)
    console.print(f"[green]Updated category {category_id}.[/green]")


@categories.command("delete")
@click.argument("category_ids", type=int, nargs=-1, required=True)
@click.confirmation_option(prompt="Delete these categories?")
@pass_context
@handle_errors
def categories_delete(ctx: MoodleContext, category_ids: tuple[int, ...]) -> None:
    """Delete course categories."""
    if preview_call(
        ctx,
        "core_course_delete_categories",
        categories=[{"id": cid, "recursive": 1} for cid in category_ids],
    ):
        return
    CourseService(ctx.get_client()).delete_categories(list(category_ids))
    console.print(f"[green]Deleted {len(category_ids)} categor(y/ies).[/green]")


@course.command()
@click.option(
    "--classification",
    type=click.Choice(["all", "inprogress", "past", "future", "favourites"]),
    default="all",
    help="Which slice of your enrolled courses.",
)
@pass_context
@handle_errors
def timeline(ctx: MoodleContext, classification: str) -> None:
    """Your enrolled courses by timeline status (in-progress / past / future)."""
    courses = ctx.get_moodle().timeline(classification)
    if ctx.json_output:
        render_json([c.to_dict() for c in courses])
    else:
        rows = [{"ID": c.id, "Short Name": c.short_name, "Full Name": c.full_name} for c in courses]
        render_table(rows, title=f"Courses · {classification} ({len(rows)})")


def _print_module(ctx: MoodleContext, cmid: int) -> None:
    cm = ctx.get_moodle().module(cmid)
    if ctx.json_output:
        render_json(cm)
    else:
        for key in ("id", "name", "modname", "instance", "course", "section", "visible", "url"):
            if key in cm:
                console.print(f"{key:10} {cm[key]}")


@course.group()
def module() -> None:
    """Course module operations."""


@module.command("show")
@click.argument("cmid", type=int)
@pass_context
@handle_errors
def module_show(ctx: MoodleContext, cmid: int) -> None:
    """Show metadata for a single course module (by course-module id)."""
    _print_module(ctx, cmid)


@module.command("add")
@click.option("--course-id", required=True, type=int)
@click.option("--section", "section_num", required=True, type=int)
@click.option(
    "--type",
    "mod_name",
    required=True,
    type=click.Choice(["label", "page", "url", "resource", "folder", "assign", "scorm"]),
)
@click.option("--name", required=True)
@click.option("--intro", default="")
@click.option("--file", "file_path", default=None, type=click.Path(exists=True, dir_okay=False))
@pass_context
@handle_errors
def module_add(
    ctx: MoodleContext,
    course_id: int,
    section_num: int,
    mod_name: str,
    name: str,
    intro: str,
    file_path: str | None,
) -> None:
    """Add a module. File/SCORM/page body uses a browser session."""
    if preview_call(
        ctx,
        "core_courseformat_create_module",
        courseid=course_id,
        modname=mod_name,
        sectionnum=section_num,
        name=name,
    ):
        return
    svc = CourseService(ctx.get_client())
    if (
        file_path
        or intro
        or mod_name in {"page", "label", "url", "resource", "folder", "scorm", "assign"}
    ):
        result = svc.add_module_via_form(course_id, section_num, mod_name, name, intro, file_path)
        if ctx.json_output:
            render_json(result)
        else:
            console.print(f"[green]Added {mod_name} '{name}'[/green]")
        return
    result = svc.create_module(course_id, mod_name, section_num)
    if ctx.json_output:
        render_json(result)
    else:
        console.print(f"[green]Added {mod_name} '{name}'[/green]")


@module.command("delete")
@click.argument("cmid", type=int)
@pass_context
@handle_errors
def module_delete(ctx: MoodleContext, cmid: int) -> None:
    """Delete a course module."""
    cm = ctx.get_moodle().module(cmid)
    course_id = int(cm.get("course") or 0)
    if preview_call(
        ctx, "core_courseformat_update_course", courseid=course_id, action="cmDelete", ids=[cmid]
    ):
        return
    CourseService(ctx.get_client()).format_update(course_id, "cmDelete", ids=[cmid])
    console.print(f"[green]Deleted module {cmid}.[/green]")


@module.command("rename")
@click.argument("cmid", type=int)
@click.option("--name", required=True)
@pass_context
@handle_errors
def module_rename(ctx: MoodleContext, cmid: int, name: str) -> None:
    """Rename a course module."""
    cm = ctx.get_moodle().module(cmid)
    course_id = int(cm.get("course") or 0)
    if preview_call(
        ctx,
        "core_courseformat_update_course",
        courseid=course_id,
        action="cmRename",
        ids=[cmid],
        name=name,
    ):
        return
    CourseService(ctx.get_client()).format_update(course_id, "cmRename", ids=[cmid], name=name)
    console.print(f"[green]Renamed module {cmid} to {name}.[/green]")


@module.command("hide")
@click.argument("cmid", type=int)
@pass_context
@handle_errors
def module_hide(ctx: MoodleContext, cmid: int) -> None:
    """Hide a course module."""
    cm = ctx.get_moodle().module(cmid)
    course_id = int(cm.get("course") or 0)
    CourseService(ctx.get_client()).format_update(course_id, "cmHide", ids=[cmid])
    console.print(f"[green]Hid module {cmid}.[/green]")


@module.command("unhide")
@click.argument("cmid", type=int)
@pass_context
@handle_errors
def module_unhide(ctx: MoodleContext, cmid: int) -> None:
    """Show a hidden course module."""
    cm = ctx.get_moodle().module(cmid)
    course_id = int(cm.get("course") or 0)
    CourseService(ctx.get_client()).format_update(course_id, "cmShow", ids=[cmid])
    console.print(f"[green]Showed module {cmid}.[/green]")


@course.command("list")
@pass_context
@handle_errors
def list_courses(ctx: MoodleContext) -> None:
    """List all courses."""
    courses = ctx.get_moodle().all_courses()
    if ctx.json_output:
        render_json([c.to_dict() for c in courses])
    else:
        rows = [
            {"ID": c.id, "Short Name": c.short_name, "Full Name": c.full_name, "Visible": c.visible}
            for c in courses
        ]
        render_table(rows, title=f"Courses ({len(rows)})")


@course.command()
@click.argument("course_id", type=int)
@pass_context
@handle_errors
def get(ctx: MoodleContext, course_id: int) -> None:
    """Get details of a course."""
    c = ctx.get_moodle().course(course_id)
    if ctx.json_output:
        render_json(c.to_dict())
    else:
        console.print(f"[bold]{c.full_name}[/bold] ({c.short_name})")
        console.print(f"ID:       {c.id}")
        console.print(f"Category: {c.category_id}")
        console.print(f"Format:   {c.format}")
        console.print(f"Visible:  {c.visible}")
        if c.summary:
            console.print(f"Summary:  {trim(c.summary, ctx.trim_messages)}")


@course.command()
@click.argument("query")
@pass_context
@handle_errors
def search(ctx: MoodleContext, query: str) -> None:
    """Search courses by name."""
    courses = ctx.get_moodle().search(query)
    if ctx.json_output:
        render_json([c.to_dict() for c in courses])
    else:
        rows = [{"ID": c.id, "Short Name": c.short_name, "Full Name": c.full_name} for c in courses]
        render_table(rows, title=f"Search results for '{query}' ({len(rows)})")


@course.command()
@click.argument("course_id", type=int)
@pass_context
@handle_errors
def contents(ctx: MoodleContext, course_id: int) -> None:
    """Show course contents (sections and modules)."""
    sections = ctx.get_moodle().course(course_id).sections
    if ctx.json_output:
        render_json([s.to_dict() for s in sections])
    else:
        for section in sections:
            console.print(f"\n[bold]{section.name}[/bold]")
            if section.summary:
                console.print(trim(section.summary, ctx.trim_messages))
            for row in section.table:
                bits = []
                for key, value in row.items():
                    if isinstance(value, list):
                        names = ", ".join(
                            str(item.get("name") or item.get("url") or "") for item in value
                        )
                        if names:
                            bits.append(f"{key}: {names}")
                    elif value:
                        bits.append(f"{key}: {value}")
                if bits:
                    console.print("  " + " | ".join(bits))
            for mod in section.activities:
                console.print(f"  [{mod.mod_name}] {mod.name}")
                if mod.text:
                    console.print(f"    {trim(mod.text, ctx.trim_messages)}")
                if mod.target:
                    console.print(f"    {mod.target}")
                for item in mod.files:
                    console.print(f"    {item.name}  {item.url}")


@course.command()
@click.argument("course")
@click.option(
    "-o",
    "--output",
    required=True,
    type=click.Path(file_okay=False),
    help="Directory to write course.json, pages, and files/",
)
@click.option("--files/--no-files", default=True, help="Download Moodle pluginfile attachments.")
@click.option(
    "--pages",
    type=click.Choice(["md", "html", "txt", "none"], case_sensitive=False),
    default="md",
    show_default=True,
    help="Save page text, tables, and links (not Moodle pluginfiles).",
)
@click.option("--deep", is_flag=True, help="Also walk forum threads and activity extras.")
@pass_context
@handle_errors
def dump(
    ctx: MoodleContext,
    course: str,
    output: str,
    files: bool,
    pages: str,
    deep: bool,
) -> None:
    """Save a module (or ``all`` enrolled courses) to a folder."""
    api = ctx.get_moodle()
    if course.lower() == "all":
        path = api.dump(output, files=files, deep=deep, pages=pages)
    else:
        path = api.course(course).dump(output, files=files, deep=deep, pages=pages)
    if ctx.json_output:
        render_json({"path": str(path)})
    else:
        console.print(f"Saved {course} to {path}")


@course.command()
@click.option("--fullname", "full_name", required=True, help="Full course name")
@click.option("--shortname", "short_name", required=True, help="Short course name")
@click.option("--categoryid", "category_id", required=True, type=int, help="Category ID")
@pass_context
@handle_errors
def create(ctx: MoodleContext, full_name: str, short_name: str, category_id: int) -> None:
    """Create a new course."""
    if preview_call(
        ctx,
        "core_course_create_courses",
        courses=[{"fullname": full_name, "shortname": short_name, "categoryid": category_id}],
    ):
        return
    svc = CourseService(ctx.get_client())
    c = svc.create_course(full_name, short_name, category_id)
    if ctx.json_output:
        render_json(c.model_dump())
    else:
        console.print(f"[green]Created course '{c.full_name}' (ID: {c.id})[/green]")


@course.command()
@click.option("--shortname", "short_name", required=True)
@click.option("--fullname", "full_name", required=True)
@click.option("--category-id", "category_id", required=True, type=int)
@click.option("--update/--no-update", default=False)
@pass_context
@handle_errors
def ensure(
    ctx: MoodleContext, short_name: str, full_name: str, category_id: int, update: bool
) -> None:
    """Create the course if the shortname is missing."""
    if preview_call(
        ctx,
        "core_course_create_courses",
        courses=[{"fullname": full_name, "shortname": short_name, "categoryid": category_id}],
        ensure=True,
        update=update,
    ):
        return
    course, created = CourseService(ctx.get_client()).ensure_course(
        short_name, full_name, category_id, update=update
    )
    if ctx.json_output:
        render_json({**course.model_dump(), "created": created})
    else:
        verb = "Created" if created else "Found"
        console.print(f"[green]{verb} course '{course.full_name}' (ID: {course.id})[/green]")


@course.command()
@click.argument("course_id", type=int)
@click.option("--fullname", "full_name", required=True)
@click.option("--shortname", "short_name", required=True)
@click.option("--categoryid", "category_id", required=True, type=int)
@pass_context
@handle_errors
def duplicate(
    ctx: MoodleContext, course_id: int, full_name: str, short_name: str, category_id: int
) -> None:
    """Duplicate a course (token-friendly copy)."""
    if preview_call(
        ctx,
        "core_course_duplicate_course",
        courseid=course_id,
        fullname=full_name,
        shortname=short_name,
        categoryid=category_id,
    ):
        return
    result = CourseService(ctx.get_client()).duplicate_course(
        course_id, full_name, short_name, category_id
    )
    if ctx.json_output:
        render_json(result)
    else:
        console.print(f"[green]Duplicated course {course_id} as {short_name}[/green]")


@course.command()
@click.argument("course_id", type=int)
@click.option("--fullname", "full_name", default=None, help="New full name")
@click.option("--shortname", "short_name", default=None, help="New short name")
@click.option("--visible", default=None, type=int, help="Visibility (0 or 1)")
@click.option("--customfield", multiple=True, help="shortname=value")
@pass_context
@handle_errors
def update(
    ctx: MoodleContext,
    course_id: int,
    full_name: str | None,
    short_name: str | None,
    visible: int | None,
    customfield: tuple[str, ...],
) -> None:
    """Update a course."""
    svc = CourseService(ctx.get_client())
    kwargs: dict[str, object] = {}
    if full_name is not None:
        kwargs["fullname"] = full_name
    if short_name is not None:
        kwargs["shortname"] = short_name
    if visible is not None:
        kwargs["visible"] = visible
    fields = parse_customfields(customfield)
    svc.update_course(course_id, custom_fields=fields or None, **kwargs)
    console.print(f"[green]Updated course {course_id}.[/green]")


@course.command()
@click.argument("course_ids", type=int, nargs=-1, required=True)
@click.confirmation_option(prompt="Are you sure you want to delete these courses?")
@pass_context
@handle_errors
def delete(ctx: MoodleContext, course_ids: tuple[int, ...]) -> None:
    """Delete courses by ID."""
    if preview_call(ctx, "core_course_delete_courses", courseids=list(course_ids)):
        return
    svc = CourseService(ctx.get_client())
    svc.delete_courses(list(course_ids))
    console.print(f"[green]Deleted {len(course_ids)} course(s).[/green]")


@course.group()
def section() -> None:
    """Course sections."""


@section.command("create")
@click.argument("course_id", type=int)
@pass_context
@handle_errors
def section_create(ctx: MoodleContext, course_id: int) -> None:
    """Add a section to a course."""
    if preview_call(
        ctx, "core_courseformat_update_course", courseid=course_id, action="sectionAdd"
    ):
        return
    result = CourseService(ctx.get_client()).format_update(course_id, "sectionAdd")
    if ctx.json_output:
        render_json(result)
    else:
        console.print(f"[green]Added a section to course {course_id}.[/green]")


@section.command("delete")
@click.argument("course_id", type=int)
@click.argument("section_id", type=int)
@pass_context
@handle_errors
def section_delete(ctx: MoodleContext, course_id: int, section_id: int) -> None:
    """Delete a section."""
    if preview_call(
        ctx,
        "core_courseformat_update_course",
        courseid=course_id,
        action="sectionDelete",
        ids=[section_id],
    ):
        return
    CourseService(ctx.get_client()).format_update(course_id, "sectionDelete", ids=[section_id])
    console.print(f"[green]Deleted section {section_id}.[/green]")


@course.command()
@click.option("-o", "--output", "dest", required=True, type=click.Path(file_okay=False))
@click.option("--course-id", "course_ids", type=int, multiple=True)
@click.option("--submissions/--no-submissions", default=True)
@click.option("--external/--no-external", default=False)
@click.option(
    "--include-visible", is_flag=True, help="Also sync courses you can see but are not enrolled in."
)
@click.option("--notify/--no-notify", default=None, help="Send notifications from the profile.")
@pass_context
@handle_errors
def sync(
    ctx: MoodleContext,
    dest: str,
    course_ids: tuple[int, ...],
    submissions: bool,
    external: bool,
    include_visible: bool,
    notify: bool | None,
) -> None:
    """Incrementally mirror course files. Keeps local copies if Moodle deletes them."""
    _, profile = ctx.config.get_profile(ctx.profile_name)
    settings = profile.sync
    ids = list(course_ids) or list(settings.course_ids)
    api = ctx.get_moodle()
    dest_path = Path(dest or settings.dest)
    dest_path.mkdir(parents=True, exist_ok=True)
    store = SyncStore(dest_path / "sync.db")
    names = settings.folder_names
    if ids:
        wanted = [api.course(cid) for cid in ids]
    else:
        wanted = list(api.courses)
        if include_visible or settings.include_visible:
            seen = {course.id for course in wanted}
            for course in api.search(""):
                if course.id not in seen:
                    wanted.append(course)
    reports = []
    try:
        for course in wanted:
            reports.append(
                sync_course(
                    course,
                    dest_path,
                    store,
                    submissions=submissions if submissions is not None else settings.submissions,
                    external=external or settings.external,
                    folder_name=names.get(str(course.id)) or names.get(course.short_name),
                    on_saved=(
                        None if ctx.json_output else lambda path: status(f"Saved {Path(path).name}")
                    ),
                )
            )
    finally:
        store.close()
    payload = [item.to_dict() for item in reports]
    if ctx.json_output:
        render_json(payload)
    else:
        downloaded = sum(len(item.downloaded) for item in reports)
        console.print(f"Synced {len(reports)} course(s), {downloaded} new file(s), to {dest}")
    should_notify = settings.notify if notify is None else notify
    if should_notify:
        sent = send_notifications(profile.notify, reports)
        if sent:
            status("Notified: " + ", ".join(sent))


@course.command()
@click.argument("course_id", type=int)
@click.option("-o", "--output", required=True, type=click.Path())
@pass_context
@handle_errors
def backup(ctx: MoodleContext, course_id: int, output: str) -> None:
    """Write a .mbz backup (browser session)."""
    path = BackupService(ctx.get_client()).backup_course(course_id, output)
    if ctx.json_output:
        render_json({"path": str(path)})
    else:
        console.print(f"[green]Wrote backup {path}[/green]")


@course.command()
@click.argument("mbz", type=click.Path(exists=True, dir_okay=False))
@click.option("--category-id", required=True, type=int)
@pass_context
@handle_errors
def restore(ctx: MoodleContext, mbz: str, category_id: int) -> None:
    """Restore a .mbz into a category (browser session)."""
    result = BackupService(ctx.get_client()).restore_course(mbz, category_id)
    if ctx.json_output:
        render_json(result)
    else:
        console.print("[green]Restore started.[/green]")

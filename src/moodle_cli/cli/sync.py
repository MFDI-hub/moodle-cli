"""Saved sync options for a profile."""

from __future__ import annotations

import json
import sys

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console, render_json


@click.group()
def sync() -> None:
    """Sync configuration (the run command is ``moodle course sync``)."""


@sync.command("config")
@click.option("--dest", default=None, type=click.Path(file_okay=False))
@click.option("--course-id", "course_ids", type=int, multiple=True)
@click.option("--folder", "folders", multiple=True, help="id=folder-name")
@click.option("--include-visible/--no-include-visible", default=None)
@click.option("--submissions/--no-submissions", default=None)
@click.option("--external/--no-external", default=None)
@click.option("--notify/--no-notify", default=None)
@pass_context
@handle_errors
def config_cmd(
    ctx: MoodleContext,
    dest: str | None,
    course_ids: tuple[int, ...],
    folders: tuple[str, ...],
    include_visible: bool | None,
    submissions: bool | None,
    external: bool | None,
    notify: bool | None,
) -> None:
    """Store default sync options on the current profile."""
    name, profile = ctx.config.get_profile(ctx.profile_name)
    settings = profile.sync
    if dest is not None:
        settings.dest = dest
    if course_ids:
        settings.course_ids = list(course_ids)
    if folders:
        mapping = dict(settings.folder_names)
        for item in folders:
            key, value = item.split("=", 1)
            mapping[key] = value
        settings.folder_names = mapping
    if include_visible is not None:
        settings.include_visible = include_visible
    if submissions is not None:
        settings.submissions = submissions
    if external is not None:
        settings.external = external
    if notify is not None:
        settings.notify = notify
    elif (
        not any([dest, course_ids, folders])
        and include_visible is None
        and submissions is None
        and sys.stdin.isatty()
    ):
        settings.dest = click.prompt("Download folder", default=settings.dest or ".")
    profile.sync = settings
    ctx.config.set_profile(name, profile)
    payload = json.loads(settings.model_dump_json())
    if ctx.json_output:
        render_json(payload)
    else:
        console.print(f"[green]Saved sync config on profile '{name}'.[/green]")
        console.print(f"Dest: {settings.dest or '(not set)'}")

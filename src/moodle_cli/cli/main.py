"""Root CLI group and shared context."""

from __future__ import annotations

import functools
import logging
import os
import sys
from typing import TYPE_CHECKING, Any

import click

from moodle_cli import __version__
from moodle_cli._utils import parse_fields
from moodle_cli.config.auth import TokenStore
from moodle_cli.config.manager import ConfigManager
from moodle_cli.exceptions import MoodleAPIError, MoodleError
from moodle_cli.output.console import error_console
from moodle_cli.output.style import output_fields, output_format, output_quiet

if TYPE_CHECKING:
    from moodle_cli.api import Moodle
    from moodle_cli.client.http import MoodleHTTPClient


class MoodleContext:
    """Shared state passed through Click context."""

    def __init__(
        self,
        profile: str | None = None,
        json_output: bool = False,
        verbose: bool = False,
        readonly: bool = False,
        trim_messages: int | None = None,
        storage_state: str | None = None,
        quiet: bool = False,
        dry_run: bool = False,
        output: str = "table",
        fields: list[str] | None = None,
    ) -> None:
        self.profile_name = profile or os.environ.get("MOODLE_PROFILE") or None
        self.output_format = "json" if json_output else output
        self.json_output = self.output_format == "json"
        self.verbose = verbose
        self.readonly = readonly
        self.storage_state = storage_state
        # None = serve the full text (the default). Set via --trim-messages N;
        # commands render long text fields through output.trim(text, this).
        self.trim_messages = trim_messages
        self.quiet = quiet
        self.dry_run = dry_run
        self.fields = fields
        self._config_mgr = ConfigManager()
        self._token_store = TokenStore()
        self._moodle: Moodle | None = None

    @property
    def config(self) -> ConfigManager:
        return self._config_mgr

    @property
    def tokens(self) -> TokenStore:
        return self._token_store

    def get_moodle(self) -> Moodle:
        """Signed-in Moodle session for this CLI invocation."""
        if self._moodle is None:
            from moodle_cli.api import Moodle

            self._moodle = Moodle.connect(
                profile=self.profile_name,
                storage_state=self.storage_state,
                readonly=self.readonly,
            )
            self._moodle.client.verbose = self.verbose
        return self._moodle

    def get_client(self) -> MoodleHTTPClient:
        """Transport used by leftover service-based commands."""
        return self.get_moodle().client


pass_context = click.make_pass_decorator(MoodleContext, ensure=True)


def handle_errors(fn: Any) -> Any:
    """Decorator that catches MoodleError and prints friendly messages."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except MoodleAPIError as exc:
            error_console.print(f"[red]Moodle API error:[/red] {exc}")
            if exc.hint:
                error_console.print(f"[yellow]Hint:[/yellow] {exc.hint}")
            if exc.debug_info:
                error_console.print(f"[dim]Debug: {exc.debug_info}[/dim]")
            sys.exit(1)
        except MoodleError as exc:
            error_console.print(f"[red]Error:[/red] {exc}")
            sys.exit(1)

    return wrapper


def apply_output_style(ctx_obj: MoodleContext) -> None:
    output_format.set(ctx_obj.output_format)
    output_fields.set(ctx_obj.fields)
    output_quiet.set(ctx_obj.quiet)


def configure_cli_logging(verbose: bool) -> None:
    """Configure library loggers from the CLI. Library modules never call basicConfig."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)


def preview_call(ctx: MoodleContext, wsfunction: str, **params: Any) -> bool:
    """Print a dry-run payload and skip the POST when ``--dry-run`` is set."""
    if not ctx.dry_run:
        return False
    from moodle_cli.output import console, render_json, render_table

    payload = {"dry_run": True, "wsfunction": wsfunction, "params": params}
    if ctx.json_output or ctx.output_format in {"json", "yaml", "csv"}:
        render_json(payload)
    else:
        console.print(f"[yellow]Dry run[/yellow] {wsfunction}")
        rows = [{"Param": key, "Value": str(value)} for key, value in params.items()]
        if rows:
            render_table(rows, title=wsfunction)
    return True


@click.group()
@click.option("--profile", "-p", default=None, help="Profile name to use (or MOODLE_PROFILE).")
@click.option(
    "--storage-state",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Playwright storage-state JSON from a logged-in browser session.",
)
@click.option(
    "--output",
    type=click.Choice(["table", "json", "yaml", "csv"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--json", "json_output", is_flag=True, help="Output as JSON (alias for --output json)."
)
@click.option("--fields", default=None, help="Comma-separated fields for json/yaml/csv output.")
@click.option(
    "--quiet", "-q", is_flag=True, help="Hide progress lines; still print results and errors."
)
@click.option("--dry-run", is_flag=True, help="Show the web-service call and do not POST it.")
@click.option("--verbose", "-v", is_flag=True, help="Show verbose output.")
@click.option(
    "--trim-messages",
    "trim_messages",
    type=click.IntRange(min=1),
    default=None,
    help=(
        "Trim long text fields (forum posts, messages, summaries, …) in table "
        "output to N chars; a trimmed value says how many chars were cut. "
        "Default: full text, never trimmed."
    ),
)
@click.version_option(version=__version__, prog_name="moodle-cli")
@click.pass_context
def cli(
    ctx: click.Context,
    profile: str | None,
    storage_state: str | None,
    output: str,
    json_output: bool,
    fields: str | None,
    quiet: bool,
    dry_run: bool,
    verbose: bool,
    trim_messages: int | None,
) -> None:
    """moodle-cli — interact with Moodle from the terminal.

    Copyright (C) 2026 Marc Alier, Juanan Pereira — LAMB Project

    Licensed under the GNU General Public License v3.0 (GPL-3.0-or-later).
    See https://github.com/Lamb-Project/moodle-cli for source code.
    """
    ctx.ensure_object(dict)
    obj = MoodleContext(
        profile=profile,
        json_output=json_output,
        verbose=verbose,
        trim_messages=trim_messages,
        storage_state=storage_state,
        quiet=quiet,
        dry_run=dry_run,
        output=output.lower(),
        fields=parse_fields(fields),
    )
    apply_output_style(obj)
    configure_cli_logging(verbose)
    ctx.obj = obj


# Import and register command groups (deferred to avoid circular imports)
def _register_commands() -> None:
    from moodle_cli.cli.activity_content import (
        database,
        glossary,
        lesson,
        wiki,
        workshop,
    )
    from moodle_cli.cli.assign import assign
    from moodle_cli.cli.auth import auth
    from moodle_cli.cli.badge import badge
    from moodle_cli.cli.blog import blog
    from moodle_cli.cli.calendar import calendar
    from moodle_cli.cli.call import call
    from moodle_cli.cli.chat import chat
    from moodle_cli.cli.choice import choice
    from moodle_cli.cli.cohort import cohort
    from moodle_cli.cli.comment import comment
    from moodle_cli.cli.competency import competency
    from moodle_cli.cli.completion import completion
    from moodle_cli.cli.content import content
    from moodle_cli.cli.course import course
    from moodle_cli.cli.enrol import enrol
    from moodle_cli.cli.feedback import feedback
    from moodle_cli.cli.file import file
    from moodle_cli.cli.forum import forum
    from moodle_cli.cli.grade import grade
    from moodle_cli.cli.group import group
    from moodle_cli.cli.h5p import h5p
    from moodle_cli.cli.message import message
    from moodle_cli.cli.note import note
    from moodle_cli.cli.quiz import quiz
    from moodle_cli.cli.rating import rating
    from moodle_cli.cli.role import role
    from moodle_cli.cli.scorm import scorm
    from moodle_cli.cli.search import search
    from moodle_cli.cli.site import site
    from moodle_cli.cli.survey import survey
    from moodle_cli.cli.sync import sync
    from moodle_cli.cli.tag import tag
    from moodle_cli.cli.user import user

    cli.add_command(auth)
    cli.add_command(site)
    cli.add_command(course)
    cli.add_command(user)
    cli.add_command(enrol)
    cli.add_command(grade)
    cli.add_command(assign)
    cli.add_command(forum)
    cli.add_command(quiz)
    cli.add_command(calendar)
    cli.add_command(message)
    cli.add_command(completion)
    cli.add_command(file)
    cli.add_command(cohort)
    cli.add_command(role)
    cli.add_command(call)
    cli.add_command(group)
    cli.add_command(feedback)
    cli.add_command(choice)
    cli.add_command(content)
    cli.add_command(badge)
    cli.add_command(note)
    cli.add_command(workshop)
    cli.add_command(glossary)
    cli.add_command(database)
    cli.add_command(wiki)
    cli.add_command(lesson)
    cli.add_command(sync)
    cli.add_command(blog)
    cli.add_command(comment)
    cli.add_command(rating)
    cli.add_command(tag)
    cli.add_command(search)
    cli.add_command(competency)
    cli.add_command(chat)
    cli.add_command(h5p)
    cli.add_command(scorm)
    cli.add_command(survey)


_register_commands()


def main() -> None:
    """Console-script entry point for ``moodle``."""
    cli.main(prog_name="moodle")

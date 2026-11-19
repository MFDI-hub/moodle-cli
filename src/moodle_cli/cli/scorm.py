"""SCORM commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import render_json
from moodle_cli.services.scorm import ScormService


@click.group()
def scorm() -> None:
    """SCORM activities."""


@scorm.command()
@click.argument("scorm_id", type=int)
@pass_context
@handle_errors
def scoes(ctx: MoodleContext, scorm_id: int) -> None:
    """List SCOs in a SCORM package."""
    render_json(ScormService(ctx.get_client()).scoes(scorm_id))


@scorm.command()
@click.argument("sco_id", type=int)
@click.option("--user-id", required=True, type=int)
@click.option("--attempt", default=1, type=int)
@pass_context
@handle_errors
def tracks(ctx: MoodleContext, sco_id: int, user_id: int, attempt: int) -> None:
    """SCORM tracking data for a user."""
    render_json(ScormService(ctx.get_client()).tracks(sco_id, user_id, attempt))


@scorm.command()
@click.argument("scorm_id", type=int)
@click.option("--user-id", required=True, type=int)
@pass_context
@handle_errors
def attempts(ctx: MoodleContext, scorm_id: int, user_id: int) -> None:
    """How many SCORM attempts a user has."""
    render_json(ScormService(ctx.get_client()).attempt_count(scorm_id, user_id))

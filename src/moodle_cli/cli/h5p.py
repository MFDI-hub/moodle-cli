"""H5P commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import render_json
from moodle_cli.services.h5p import H5PService


@click.group()
def h5p() -> None:
    """H5P activities."""


@h5p.command()
@click.argument("h5pactivity_id", type=int)
@click.option("--user-id", type=int, default=None)
@pass_context
@handle_errors
def attempts(ctx: MoodleContext, h5pactivity_id: int, user_id: int | None) -> None:
    """List H5P attempts."""
    render_json(H5PService(ctx.get_client()).attempts(h5pactivity_id, user_id))


@h5p.command()
@click.argument("h5pactivity_id", type=int)
@click.option("--attempt-id", type=int, default=None)
@pass_context
@handle_errors
def results(ctx: MoodleContext, h5pactivity_id: int, attempt_id: int | None) -> None:
    """Show H5P results."""
    render_json(H5PService(ctx.get_client()).results(h5pactivity_id, attempt_id))

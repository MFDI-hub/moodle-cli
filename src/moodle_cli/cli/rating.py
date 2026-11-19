"""Rating commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console, render_json
from moodle_cli.services.rating import RatingService


@click.group()
def rating() -> None:
    """Ratings."""


@rating.command("list")
@click.option("--contextlevel", required=True)
@click.option("--instanceid", required=True, type=int)
@click.option("--component", required=True)
@click.option("--ratingarea", required=True)
@click.option("--itemid", required=True, type=int)
@click.option("--scaleid", required=True, type=int)
@pass_context
@handle_errors
def list_ratings(
    ctx: MoodleContext,
    contextlevel: str,
    instanceid: int,
    component: str,
    ratingarea: str,
    itemid: int,
    scaleid: int,
) -> None:
    """List ratings on an item."""
    data = RatingService(ctx.get_client()).list_ratings(
        contextlevel, instanceid, component, ratingarea, itemid, scaleid
    )
    render_json(data) if ctx.json_output else console.print(data)


@rating.command()
@click.option("--contextlevel", required=True)
@click.option("--instanceid", required=True, type=int)
@click.option("--component", required=True)
@click.option("--ratingarea", required=True)
@click.option("--itemid", required=True, type=int)
@click.option("--scaleid", required=True, type=int)
@click.option("--rating", "value", required=True, type=int)
@pass_context
@handle_errors
def add(
    ctx: MoodleContext,
    contextlevel: str,
    instanceid: int,
    component: str,
    ratingarea: str,
    itemid: int,
    scaleid: int,
    value: int,
) -> None:
    """Add a rating."""
    result = RatingService(ctx.get_client()).add(
        contextlevel, instanceid, component, ratingarea, itemid, scaleid, value
    )
    if ctx.json_output:
        render_json(result)
    else:
        console.print("[green]Added rating.[/green]")

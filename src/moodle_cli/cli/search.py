"""Site search commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import render_json, render_table
from moodle_cli.services.search import SearchService


@click.group()
def search() -> None:
    """Global site search."""


@search.command("query")
@click.argument("text")
@click.option("--page", default=0, type=int)
@pass_context
@handle_errors
def query(ctx: MoodleContext, text: str, page: int) -> None:
    """Search the site. Fails clearly when global search is off."""
    data = SearchService(ctx.get_client()).results(text, page)
    if ctx.json_output:
        render_json(data)
    else:
        rows = data.get("results", data) if isinstance(data, dict) else data
        if isinstance(rows, list):
            table = [
                {
                    "Title": r.get("title") or r.get("name", ""),
                    "Area": r.get("areaid") or r.get("component", ""),
                }
                for r in rows
                if isinstance(r, dict)
            ]
            render_table(table, title=f"Search ({len(table)})")
        else:
            render_json(data)

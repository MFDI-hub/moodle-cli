"""Blog commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console, render_json, render_table
from moodle_cli.services.blog import BlogService


@click.group()
def blog() -> None:
    """Site blogs."""


@blog.command()
@click.option("--userid", type=int, default=None)
@pass_context
@handle_errors
def entries(ctx: MoodleContext, userid: int | None) -> None:
    """List blog entries."""
    params = {} if userid is None else {"filters": [{"name": "userid", "value": str(userid)}]}
    rows = BlogService(ctx.get_client()).entries(**params)
    if ctx.json_output:
        render_json(rows)
    else:
        table = [
            {"ID": e.get("id"), "Subject": e.get("subject", ""), "Author": e.get("userid")}
            for e in rows
        ]
        render_table(table, title=f"Blog entries ({len(table)})")


@blog.command()
@click.option("--subject", required=True)
@click.option("--summary", required=True)
@pass_context
@handle_errors
def add(ctx: MoodleContext, subject: str, summary: str) -> None:
    """Create a blog entry if the site exposes core_blog_add_entry."""
    result = BlogService(ctx.get_client()).add(subject, summary)
    if ctx.json_output:
        render_json(result)
    else:
        console.print("[green]Created blog entry.[/green]")

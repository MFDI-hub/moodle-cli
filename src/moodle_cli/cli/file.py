"""File commands."""

from __future__ import annotations

import click

from moodle_cli.api.models import FileRef
from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console, render_json, render_table
from moodle_cli.services.file import FileService


@click.group()
def file() -> None:
    """File management."""


@file.command("list")
@click.argument("context_id", type=int)
@click.option("--component", default="user", help="File component")
@click.option("--filearea", "file_area", default="private", help="File area")
@click.option("--itemid", "item_id", default=0, type=int, help="Item ID")
@click.option("--filepath", "file_path", default="/", help="File path")
@pass_context
@handle_errors
def list_files(
    ctx: MoodleContext,
    context_id: int,
    component: str,
    file_area: str,
    item_id: int,
    file_path: str,
) -> None:
    """List files in a Moodle file area."""
    files = ctx.get_moodle().list_files(context_id, component, file_area, item_id, file_path)
    if ctx.json_output:
        render_json([f.to_dict() for f in files])
    else:
        rows = [{"Name": f.name, "URL": f.url} for f in files]
        render_table(rows, title=f"Files ({len(rows)})")


@file.command("get")
@click.argument("url")
@click.option("--output", "-o", default=None, help="Destination file or directory")
@pass_context
@handle_errors
def get_file(ctx: MoodleContext, url: str, output: str | None) -> None:
    """Download a Moodle file URL (pluginfile.php) with the current session."""
    path = FileRef(_api=ctx.get_moodle(), name="", url=url).download(output)
    if ctx.json_output:
        render_json({"path": str(path), "filename": path.name, "size": path.stat().st_size})
    else:
        console.print(f"Saved {path.name} ({path.stat().st_size} bytes) to {path}")


@file.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--component", default="user", help="File component")
@click.option("--filearea", "file_area", default="draft", help="File area")
@click.option("--itemid", "item_id", default=0, type=int, help="Item ID")
@pass_context
@handle_errors
def upload(
    ctx: MoodleContext,
    file_path: str,
    component: str,
    file_area: str,
    item_id: int,
) -> None:
    """Upload a file to Moodle."""
    svc = FileService(ctx.get_client())
    result = svc.upload(file_path, component, file_area, item_id)
    if ctx.json_output:
        render_json(result)
    else:
        console.print("[green]Uploaded file successfully.[/green]")
        if isinstance(result, list) and result:
            console.print(f"Item ID: {result[0].get('itemid', 'N/A')}")

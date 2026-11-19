"""Chat commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console, render_json, render_table
from moodle_cli.services.chat import ChatService


@click.group()
def chat() -> None:
    """Chat activities."""


@chat.command()
@click.argument("chat_id", type=int)
@pass_context
@handle_errors
def sessions(ctx: MoodleContext, chat_id: int) -> None:
    """List chat sessions."""
    data = ChatService(ctx.get_client()).sessions(chat_id)
    render_json(data) if ctx.json_output else console.print(data)


@chat.command()
@click.argument("chat_id", type=int)
@click.option("--start", default=0, type=int)
@click.option("--end", default=0, type=int)
@pass_context
@handle_errors
def messages(ctx: MoodleContext, chat_id: int, start: int, end: int) -> None:
    """List messages in a chat session."""
    data = ChatService(ctx.get_client()).messages(chat_id, start, end)
    if ctx.json_output:
        render_json(data)
    else:
        rows = data.get("messages", data) if isinstance(data, dict) else data
        table = [
            {"ID": m.get("id"), "User": m.get("userid"), "Message": m.get("message", "")}
            for m in (rows or [])
            if isinstance(m, dict)
        ]
        render_table(table, title=f"Messages ({len(table)})")


@chat.command()
@click.argument("chat_id", type=int)
@click.option("--message", required=True)
@pass_context
@handle_errors
def send(ctx: MoodleContext, chat_id: int, message: str) -> None:
    """Send a chat message."""
    result = ChatService(ctx.get_client()).send(chat_id, message)
    if ctx.json_output:
        render_json(result)
    else:
        console.print("[green]Sent.[/green]")

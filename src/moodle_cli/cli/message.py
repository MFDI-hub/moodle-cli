"""Message commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console, render_json, render_table, trim
from moodle_cli.services.message import MessageService


@click.group()
def message() -> None:
    """Messaging."""


@message.command()
@pass_context
@handle_errors
def unread(ctx: MoodleContext) -> None:
    """Number of conversations with unread messages."""
    count = ctx.get_moodle().unread_count()
    if ctx.json_output:
        render_json({"unread_conversations": count})
    else:
        console.print(f"Unread conversations: [bold]{count}[/bold]")


@message.command()
@click.argument("user_id", type=int)
@click.argument("text")
@pass_context
@handle_errors
def send(ctx: MoodleContext, user_id: int, text: str) -> None:
    """Send a message to a user."""
    svc = MessageService(ctx.get_client())
    msg_id = svc.send_message(user_id, text)
    console.print(f"[green]Sent message {msg_id} to user {user_id}[/green]")


@message.command("list")
@click.option("--from-user", type=int, default=0, help="Filter by sender user ID")
@pass_context
@handle_errors
def list_messages(ctx: MoodleContext, from_user: int) -> None:
    """List recent messages."""
    api = ctx.get_moodle()
    if from_user:
        msgs = MessageService(api.client).get_messages(api.me.id, user_id_from=from_user)
        payload = [m.model_dump() for m in msgs]
        rows = [
            {
                "ID": m.id,
                "From": m.user_id_from,
                "Text": trim(m.text, ctx.trim_messages),
                "Time": m.time_created,
            }
            for m in msgs
        ]
    else:
        items = api.messages
        payload = [m.to_dict() for m in items]
        rows = [
            {
                "ID": m.id,
                "From": m.from_id,
                "Text": trim(m.text, ctx.trim_messages),
                "Time": m.time_created,
            }
            for m in items
        ]
    if ctx.json_output:
        render_json(payload)
    else:
        render_table(rows, title=f"Messages ({len(rows)})")


@message.command()
@pass_context
@handle_errors
def conversations(ctx: MoodleContext) -> None:
    """List conversations."""
    convs = ctx.get_moodle().conversations
    if ctx.json_output:
        render_json([c.to_dict() for c in convs])
    else:
        rows = [
            {
                "ID": c.id,
                "Name": c.name or "(unnamed)",
                "Members": c.member_count,
                "Unread": c.unread,
            }
            for c in convs
        ]
        render_table(rows, title=f"Conversations ({len(rows)})")

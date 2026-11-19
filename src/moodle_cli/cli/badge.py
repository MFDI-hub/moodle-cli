"""Badge commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import fmt_ts, render_json, render_table
from moodle_cli.services.badge import BadgeService


@click.group()
def badge() -> None:
    """Badges."""


@badge.command("user")
@click.option("--user-id", type=int, default=None, help="User ID (defaults to current user).")
@click.option("--course-id", type=int, default=None, help="Limit to badges from one course.")
@pass_context
@handle_errors
def user_badges(ctx: MoodleContext, user_id: int | None, course_id: int | None) -> None:
    """List a user's awarded badges."""
    api = ctx.get_moodle()
    if user_id is None and course_id is None:
        badges = api.badges
        if ctx.json_output:
            render_json([b.to_dict() for b in badges])
        else:
            rows = [
                {"ID": b.id, "Name": b.name, "Issued": fmt_ts(b.date_issued), "Issuer": b.issuer}
                for b in badges
            ]
            render_table(rows, title=f"Badges ({len(rows)})")
        return
    if user_id is None:
        user_id = api.me.id
    items = BadgeService(api.client).user_badges(user_id, course_id)
    if ctx.json_output:
        render_json([b.model_dump() for b in items])
    else:
        rows = [
            {"ID": b.id, "Name": b.name, "Issued": fmt_ts(b.date_issued), "Issuer": b.issuer_name}
            for b in items
        ]
        render_table(rows, title=f"Badges ({len(rows)})")

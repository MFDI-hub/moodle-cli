"""Group commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console, render_json, render_table
from moodle_cli.services.group import GroupService


@click.group()
def group() -> None:
    """Groups and groupings."""


@group.command("list")
@click.argument("course_id", type=int)
@pass_context
@handle_errors
def list_groups(ctx: MoodleContext, course_id: int) -> None:
    """List groups in a course."""
    groups = ctx.get_moodle().course(course_id).groups
    if ctx.json_output:
        render_json([g.to_dict() for g in groups])
    else:
        rows = [{"ID": g.id, "Name": g.name} for g in groups]
        render_table(rows, title=f"Groups ({len(rows)})")


@group.command()
@click.argument("course_id", type=int)
@pass_context
@handle_errors
def groupings(ctx: MoodleContext, course_id: int) -> None:
    """List groupings in a course."""
    items = ctx.get_moodle().course(course_id).groupings
    if ctx.json_output:
        render_json([g.to_dict() for g in items])
    else:
        rows = [{"ID": g.id, "Name": g.name} for g in items]
        render_table(rows, title=f"Groupings ({len(rows)})")


@group.command("user-groups")
@click.argument("course_id", type=int)
@click.argument("user_id", type=int)
@pass_context
@handle_errors
def user_groups(ctx: MoodleContext, course_id: int, user_id: int) -> None:
    """List the groups a user belongs to in a course."""
    svc = GroupService(ctx.get_client())
    groups = svc.user_groups(course_id, user_id)
    if ctx.json_output:
        render_json([g.model_dump() for g in groups])
    else:
        rows = [{"ID": g.id, "Name": g.name} for g in groups]
        render_table(rows, title=f"Groups for user {user_id} ({len(rows)})")


@group.command()
@click.argument("course_id", type=int)
@click.option("--name", required=True)
@click.option("--description", default="")
@pass_context
@handle_errors
def create(ctx: MoodleContext, course_id: int, name: str, description: str) -> None:
    """Create a group."""
    groups = GroupService(ctx.get_client()).create_groups(course_id, name, description)
    if ctx.json_output:
        render_json([g.model_dump() for g in groups])
    else:
        console.print(f"[green]Created group '{name}'[/green]")


@group.command()
@click.argument("group_ids", type=int, nargs=-1, required=True)
@pass_context
@handle_errors
def delete(ctx: MoodleContext, group_ids: tuple[int, ...]) -> None:
    """Delete groups."""
    GroupService(ctx.get_client()).delete_groups(list(group_ids))
    console.print(f"[green]Deleted {len(group_ids)} group(s).[/green]")


@group.command("add-members")
@click.argument("group_id", type=int)
@click.argument("user_ids", type=int, nargs=-1, required=True)
@pass_context
@handle_errors
def add_members(ctx: MoodleContext, group_id: int, user_ids: tuple[int, ...]) -> None:
    """Add users to a group."""
    GroupService(ctx.get_client()).add_members(group_id, list(user_ids))
    console.print(f"[green]Added {len(user_ids)} member(s) to group {group_id}.[/green]")


@group.command("remove-members")
@click.argument("group_id", type=int)
@click.argument("user_ids", type=int, nargs=-1, required=True)
@pass_context
@handle_errors
def remove_members(ctx: MoodleContext, group_id: int, user_ids: tuple[int, ...]) -> None:
    """Remove users from a group."""
    GroupService(ctx.get_client()).remove_members(group_id, list(user_ids))
    console.print(f"[green]Removed {len(user_ids)} member(s) from group {group_id}.[/green]")


@group.command("create-grouping")
@click.argument("course_id", type=int)
@click.option("--name", required=True)
@click.option("--description", default="")
@pass_context
@handle_errors
def create_grouping(ctx: MoodleContext, course_id: int, name: str, description: str) -> None:
    """Create a grouping."""
    result = GroupService(ctx.get_client()).create_grouping(course_id, name, description)
    if ctx.json_output:
        render_json(result)
    else:
        console.print(f"[green]Created grouping '{name}'[/green]")


@group.command("assign-grouping")
@click.argument("grouping_id", type=int)
@click.argument("group_ids", type=int, nargs=-1, required=True)
@pass_context
@handle_errors
def assign_grouping(ctx: MoodleContext, grouping_id: int, group_ids: tuple[int, ...]) -> None:
    """Put groups into a grouping."""
    GroupService(ctx.get_client()).assign_grouping(grouping_id, list(group_ids))
    console.print(f"[green]Assigned {len(group_ids)} group(s) to grouping {grouping_id}.[/green]")

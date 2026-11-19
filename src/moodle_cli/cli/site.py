"""Site commands: info, functions."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console, render_json, render_table


@click.group()
def site() -> None:
    """Site information and discovery."""


@site.command()
@pass_context
@handle_errors
def info(ctx: MoodleContext) -> None:
    """Show site information."""
    si = ctx.get_moodle().site
    if ctx.json_output:
        render_json(si.to_dict())
    else:
        console.print(f"[bold]{si.name}[/bold]")
        console.print(f"URL:      {si.url}")
        console.print(f"Release:  {si.release}")
        console.print(f"Version:  {si.version}")
        console.print(f"User:     {si.full_name} ({si.username})")
        console.print(f"Language: {si.lang}")


@site.command()
@click.option("--search", "-s", default=None, help="Filter functions by name")
@click.option(
    "--component", "-c", default=None, help="Filter by component prefix (e.g. core_course)"
)
@pass_context
@handle_errors
def functions(ctx: MoodleContext, search: str | None, component: str | None) -> None:
    """List available web service functions."""
    funcs = list(ctx.get_moodle().site.functions)
    if search:
        funcs = [name for name in funcs if search.lower() in name.lower()]
    if component:
        funcs = [name for name in funcs if name.startswith(component)]
    if ctx.json_output:
        render_json(funcs)
    else:
        rows = [{"Function": name} for name in funcs]
        render_table(rows, title=f"Functions ({len(rows)})")


@site.command()
@pass_context
@handle_errors
def doctor(ctx: MoodleContext) -> None:
    """Check URL, credentials, and site info. Secrets are redacted."""
    from moodle_cli._utils import redact

    name, profile = ctx.config.get_profile(ctx.profile_name)
    token = ctx.tokens.get(name)
    checks: list[dict[str, object]] = [
        {"check": "profile", "ok": True, "detail": name},
        {"check": "url", "ok": bool(profile.url), "detail": profile.url},
        {
            "check": "credentials",
            "ok": bool(token or profile.storage_state),
            "detail": "session" if profile.storage_state else ("token" if token else "missing"),
        },
    ]
    try:
        info = ctx.get_moodle().site
        checks.append(
            {
                "check": "site info",
                "ok": True,
                "detail": redact({"name": info.name, "user": info.username, "url": info.url}),
            }
        )
    except Exception as exc:
        checks.append({"check": "site info", "ok": False, "detail": str(exc)})
    if ctx.json_output:
        render_json(checks)
    else:
        for row in checks:
            mark = "ok" if row["ok"] else "FAIL"
            console.print(f"{mark:4} {row['check']}: {row['detail']}")

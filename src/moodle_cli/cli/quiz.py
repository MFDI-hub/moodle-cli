"""Quiz commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console, render_json, render_table, trim
from moodle_cli.services.quiz import QuizService


@click.group()
def quiz() -> None:
    """Quiz management."""


@quiz.command("best-grade")
@click.argument("quiz_id", type=int)
@click.option("--user-id", type=int, default=None, help="User ID (defaults to current user)")
@pass_context
@handle_errors
def best_grade(ctx: MoodleContext, quiz_id: int, user_id: int | None) -> None:
    """Show a user's best grade on a quiz."""
    svc = QuizService(ctx.get_client())
    data = svc.best_grade(quiz_id, user_id)
    if ctx.json_output:
        render_json(data)
    else:
        if data.get("hasgrade"):
            console.print(f"Best grade: {data.get('grade')}")
        else:
            console.print("No grade yet.")


@quiz.command("list")
@click.argument("course_id", type=int)
@pass_context
@handle_errors
def list_quizzes(ctx: MoodleContext, course_id: int) -> None:
    """List quizzes in a course."""
    quizzes = ctx.get_moodle().course(course_id).quizzes
    if ctx.json_output:
        render_json([q.to_dict() for q in quizzes])
    else:
        rows = [{"ID": q.id, "Name": q.name, "Grade": q.grade} for q in quizzes]
        render_table(rows, title=f"Quizzes ({len(rows)})")


@quiz.command()
@click.argument("attempt_id", type=int)
@pass_context
@handle_errors
def review(ctx: MoodleContext, attempt_id: int) -> None:
    """Full review of a finished attempt — questions, marks, feedback."""
    data = QuizService(ctx.get_client()).attempt_review(attempt_id)
    if ctx.json_output:
        render_json(data)
    else:
        import re as _re

        grade = data.get("grade", "-")
        console.print(f"Grade: [bold]{grade}[/bold]")
        for q in data.get("questions", []):
            status = q.get("status", "")
            mark = q.get("mark", "")
            slot = q.get("slot", "")
            html = _re.sub(r"<[^>]+>", " ", q.get("html", "") or "")
            html = trim(_re.sub(r"\s+", " ", html).strip(), ctx.trim_messages)
            console.print(f"  Q{slot} [{status}] mark={mark}: {html}")


@quiz.command()
@click.argument("quiz_id", type=int)
@click.option("--user-id", type=int, default=None, help="Filter by user ID")
@pass_context
@handle_errors
def attempts(ctx: MoodleContext, quiz_id: int, user_id: int | None) -> None:
    """List quiz attempts."""
    svc = QuizService(ctx.get_client())
    atts = svc.get_attempts(quiz_id, user_id)
    if ctx.json_output:
        render_json([a.model_dump() for a in atts])
    else:
        rows = [
            {
                "ID": a.id,
                "User": a.user_id,
                "Attempt": a.attempt,
                "State": a.state,
                "Grade": a.grade or "",
            }
            for a in atts
        ]
        render_table(rows, title=f"Attempts ({len(rows)})")


@quiz.command()
@click.argument("quiz_id", type=int)
@pass_context
@handle_errors
def start(ctx: MoodleContext, quiz_id: int) -> None:
    """Start a quiz attempt."""
    data = QuizService(ctx.get_client()).start_attempt(quiz_id)
    if ctx.json_output:
        render_json(data)
    else:
        attempt = data.get("attempt") or data
        console.print(f"[green]Started attempt {attempt.get('id', attempt)}[/green]")


@quiz.command("questions")
@click.argument("attempt_id", type=int)
@click.option("--page", default=0, type=int)
@pass_context
@handle_errors
def questions(ctx: MoodleContext, attempt_id: int, page: int) -> None:
    """List questions on an in-progress attempt."""
    data = QuizService(ctx.get_client()).attempt_data(attempt_id, page)
    if ctx.json_output:
        render_json(data)
    else:
        rows = [
            {"Slot": q.get("slot"), "Type": q.get("type"), "Status": q.get("status")}
            for q in data.get("questions", [])
        ]
        render_table(rows, title=f"Questions ({len(rows)})")


@quiz.command()
@click.argument("attempt_id", type=int)
@click.option("--answer", "answers", multiple=True, help="name=value (Moodle question field)")
@pass_context
@handle_errors
def save(ctx: MoodleContext, attempt_id: int, answers: tuple[str, ...]) -> None:
    """Save answers on an in-progress attempt."""
    payload = dict(item.split("=", 1) for item in answers)
    result = QuizService(ctx.get_client()).save_attempt(attempt_id, payload)
    if ctx.json_output:
        render_json(result)
    else:
        console.print(f"[green]Saved attempt {attempt_id}.[/green]")


@quiz.command("process")
@click.argument("attempt_id", type=int)
@click.option("--answer", "answers", multiple=True, help="name=value")
@click.option("--finish", is_flag=True, help="Submit the attempt.")
@pass_context
@handle_errors
def process(ctx: MoodleContext, attempt_id: int, answers: tuple[str, ...], finish: bool) -> None:
    """Process (and optionally finish) a quiz attempt."""
    payload = dict(item.split("=", 1) for item in answers)
    result = QuizService(ctx.get_client()).process_attempt(attempt_id, payload, finish=finish)
    if ctx.json_output:
        render_json(result)
    else:
        console.print(f"[green]Processed attempt {attempt_id}.[/green]")

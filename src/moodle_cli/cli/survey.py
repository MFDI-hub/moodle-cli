"""Survey commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import render_json
from moodle_cli.services.survey import SurveyService


@click.group()
def survey() -> None:
    """Survey activities."""


@survey.command()
@click.argument("survey_id", type=int)
@click.option("--cmid", default=0, type=int)
@pass_context
@handle_errors
def questions(ctx: MoodleContext, survey_id: int, cmid: int) -> None:
    """Survey questions."""
    render_json(SurveyService(ctx.get_client()).questions(survey_id, cmid))


@survey.command()
@click.argument("survey_id", type=int)
@click.option("--cmid", default=0, type=int)
@pass_context
@handle_errors
def responses(ctx: MoodleContext, survey_id: int, cmid: int) -> None:
    """Survey answers, or the survey page when the web service is missing."""
    render_json(SurveyService(ctx.get_client()).responses(survey_id, cmid))

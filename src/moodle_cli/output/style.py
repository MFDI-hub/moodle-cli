"""Process-wide output format selected by the root CLI flags."""

from __future__ import annotations

from contextvars import ContextVar

output_format: ContextVar[str] = ContextVar("output_format", default="table")
output_fields: ContextVar[list[str] | None] = ContextVar("output_fields", default=None)
output_quiet: ContextVar[bool] = ContextVar("output_quiet", default=False)

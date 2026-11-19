"""JSON / YAML / CSV writers used by the table and json helpers."""

from __future__ import annotations

import csv
import json as _json
import sys
from typing import Any

from moodle_cli.output.style import output_fields, output_format


def pick_fields(data: Any, fields: list[str] | None) -> Any:
    if not fields:
        return data
    if isinstance(data, list):
        return [pick_fields(item, fields) for item in data]
    if isinstance(data, dict):
        missing = [name for name in fields if name not in data]
        if missing:
            raise ValueError(f"Unknown field(s): {', '.join(missing)}")
        return {name: data[name] for name in fields}
    return data


def as_rows(data: Any) -> list[dict[str, Any]]:
    if data is None:
        return []
    if isinstance(data, list):
        rows: list[dict[str, Any]] = []
        for item in data:
            if isinstance(item, dict):
                rows.append(item)
            else:
                rows.append({"value": item})
        return rows
    if isinstance(data, dict):
        return [data]
    return [{"value": data}]


def write_machine(data: Any) -> None:
    fmt = output_format.get()
    try:
        payload = pick_fields(data, output_fields.get())
    except ValueError as exc:
        from moodle_cli.exceptions import MoodleError

        raise MoodleError(str(exc)) from exc
    if fmt == "yaml":
        import yaml

        sys.stdout.write(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))
        return
    if fmt == "csv":
        rows = as_rows(payload)
        if not rows:
            return
        fields = output_fields.get() or list(rows[0].keys())
        writer = csv.DictWriter(sys.stdout, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _cell(row.get(key)) for key in fields})
        return
    sys.stdout.write(_json.dumps(payload, default=str, indent=2, ensure_ascii=False) + "\n")


def machine_format() -> bool:
    return output_format.get() in {"json", "yaml", "csv"}


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return _json.dumps(value, default=str, ensure_ascii=False)
    return str(value)

"""Compare incoming schema snapshots and detect drift from the last version."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SchemaDriftResult:
    """Outcome of comparing two schema snapshots."""

    has_drift: bool
    added_columns: tuple[str, ...]
    removed_columns: tuple[str, ...]
    type_changes: tuple[tuple[str, str, str], ...]


def _column_map(schema_snapshot: dict | None) -> dict[str, str]:
    columns = (schema_snapshot or {}).get("columns", [])
    mapping: dict[str, str] = {}
    for column in columns:
        if isinstance(column, dict) and column.get("name"):
            mapping[str(column["name"])] = str(column.get("type", "string"))
    return mapping


def detect_schema_drift(
    previous: dict | None,
    incoming: dict,
) -> SchemaDriftResult:
    """Return drift details when column names or types differ."""
    if not previous:
        return SchemaDriftResult(False, (), (), ())

    prev_map = _column_map(previous)
    next_map = _column_map(incoming)
    prev_names = set(prev_map)
    next_names = set(next_map)
    added = tuple(sorted(next_names - prev_names))
    removed = tuple(sorted(prev_names - next_names))
    type_changes: list[tuple[str, str, str]] = []
    for name in sorted(prev_names & next_names):
        if prev_map[name] != next_map[name]:
            type_changes.append((name, prev_map[name], next_map[name]))

    has_drift = bool(added or removed or type_changes)
    return SchemaDriftResult(
        has_drift=has_drift,
        added_columns=added,
        removed_columns=removed,
        type_changes=tuple(type_changes),
    )

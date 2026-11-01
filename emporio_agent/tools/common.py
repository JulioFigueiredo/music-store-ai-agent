"""Types and small helpers shared by the tool modules."""

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import pandas as pd

# A table row as a plain dict.
Record = dict[str, Any]
# What every tool returns to the model: a small, JSON-serializable dict.
ToolResult = dict[str, Any]


def to_records(table: pd.DataFrame) -> list[Record]:
    """DataFrame rows as plain dicts, which keeps the tool code simple."""
    return [
        {str(key): value for key, value in row.items()}
        for row in table.to_dict("records")
    ]


def group_by(records: list[Record], key: str) -> dict[Any, list[Record]]:
    """Group records by one field: {value: [records with that value]}."""
    groups: dict[Any, list[Record]] = defaultdict(list)
    for record in records:
        groups[record[key]].append(record)
    return dict(groups)


def to_int(value: Any) -> int | None:
    """Convert a model-provided number ("8", 8.0) to int, or None."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_money(value: float) -> float:
    """Round to cents, half up like a cashier (569.905 -> 569.91).

    Plain round() works on binary floats and can round 569.905 down.
    """
    cents = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(cents)


def format_date(value: date | None) -> str | None:
    """Format a date the Brazilian way (25/03/2026)."""
    return value.strftime("%d/%m/%Y") if value else None

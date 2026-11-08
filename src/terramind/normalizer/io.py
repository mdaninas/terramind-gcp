"""Bounded JSON I/O. Never include source data in validation errors."""

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from terramind.errors import InputError
from terramind.schemas.normalized import MAX_REQUEST_BYTES, NormalizedPlan


def read_bounded(path: Path, limit: int) -> bytes:
    try:
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
    except OSError:
        raise InputError("Unable to read input file") from None
    if len(data) > limit:
        raise InputError("Input exceeds the permitted byte limit")
    return data


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InputError("Duplicate JSON keys are not permitted")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise InputError("Non-finite JSON numbers are not permitted")


def parse_json(data: bytes, limit: int) -> dict[str, Any]:
    if len(data) > limit:
        raise InputError("Input exceeds the permitted byte limit")
    try:
        value = json.loads(data, object_pairs_hook=_object, parse_constant=_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise InputError("Invalid JSON: check syntax, duplicate keys and nesting") from None
    if not isinstance(value, dict):
        raise InputError("Input must be a JSON object")
    pending = [(value, 0)]
    while pending:
        node, depth = pending.pop()
        if depth > 64:
            raise InputError("JSON nesting exceeds 64 levels")
        if isinstance(node, dict):
            pending.extend((child, depth + 1) for child in node.values())
        elif isinstance(node, list):
            pending.extend((child, depth + 1) for child in node)
    return value


def load_normalized(data: bytes) -> NormalizedPlan:
    parse_json(data, MAX_REQUEST_BYTES)
    try:
        return NormalizedPlan.model_validate_json(data)
    except ValidationError:
        raise InputError("Normalized schema validation failed; see schema v1.0") from None

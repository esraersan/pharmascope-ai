"""JSON and JSONL serialization for evaluation artifacts."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from pharmascope.evals.models import EvalTask

ModelT = TypeVar("ModelT", bound=BaseModel)


def load_jsonl(path: str | Path, model: type[ModelT]) -> list[ModelT]:
    """Load validated models from a UTF-8 JSONL file."""
    records: list[ModelT] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(model.model_validate_json(line))
            except (ValueError, json.JSONDecodeError) as error:
                raise ValueError(
                    f"invalid record at {path}:{line_number}: {error}"
                ) from error
    return records


def write_jsonl(path: str | Path, records: Iterable[BaseModel]) -> None:
    """Write models as deterministic UTF-8 JSONL."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(record.model_dump_json(exclude_none=True))
            handle.write("\n")


def load_tasks(path: str | Path) -> list[EvalTask]:
    """Load tasks from either a JSON array or JSONL file."""
    source = Path(path)
    if source.suffix.casefold() == ".jsonl":
        return load_jsonl(source, EvalTask)
    with source.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON array of tasks")
    return [EvalTask.model_validate(item) for item in payload]

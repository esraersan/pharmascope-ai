"""Deterministic graders for structured scientific-agent responses."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from typing import Any

from pharmascope.evals.models import (
    CandidateResponse,
    EvalTask,
    Grade,
    GraderKind,
)


def _normalized(value: Any) -> str:
    return " ".join(str(value).split()).casefold()


def _as_set(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        values: Iterable[Any] = re.split(r"[,;\n]", value)
    elif isinstance(value, (list, tuple, set, frozenset)):
        values = value
    else:
        values = [value]
    return {_normalized(item) for item in values if _normalized(item)}


def _set_grade(
    grader: GraderKind, expected: set[str], actual: set[str]
) -> Grade:
    if not expected and not actual:
        score = 1.0
    elif not expected or not actual:
        score = 0.0
    else:
        precision = len(expected & actual) / len(actual)
        recall = len(expected & actual) / len(expected)
        score = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
    return Grade(
        grader=grader,
        score=score,
        passed=actual == expected,
        details={
            "missing": sorted(expected - actual),
            "unexpected": sorted(actual - expected),
        },
    )


def grade_exact(task: EvalTask, response: CandidateResponse) -> Grade:
    expected = _normalized(task.reference.exact)
    actual = _normalized(response.answer)
    passed = actual == expected
    return Grade(
        grader=GraderKind.EXACT,
        score=float(passed),
        passed=passed,
        details={"expected": expected, "actual": actual},
    )


def grade_set(task: EvalTask, response: CandidateResponse) -> Grade:
    expected = _as_set(task.reference.set_values)
    actual = _as_set(response.answer)
    return _set_grade(GraderKind.SET, expected, actual)


def grade_numeric(task: EvalTask, response: CandidateResponse) -> Grade:
    expected = task.reference.numeric
    assert expected is not None
    try:
        actual = float(response.answer)
    except (TypeError, ValueError):
        return Grade(
            grader=GraderKind.NUMERIC,
            score=0.0,
            passed=False,
            details={"expected": expected, "actual": response.answer},
        )

    tolerance = max(
        task.reference.absolute_tolerance,
        abs(expected) * task.reference.relative_tolerance,
    )
    difference = abs(actual - expected)
    passed = math.isfinite(actual) and math.isclose(
        actual,
        expected,
        rel_tol=task.reference.relative_tolerance,
        abs_tol=task.reference.absolute_tolerance,
    )
    return Grade(
        grader=GraderKind.NUMERIC,
        score=float(passed),
        passed=passed,
        details={
            "expected": expected,
            "actual": actual,
            "difference": difference,
            "tolerance": tolerance,
        },
    )


def grade_citations(task: EvalTask, response: CandidateResponse) -> Grade:
    expected = {
        (item.source.value, _normalized(item.identifier))
        for item in task.reference.evidence
    }
    actual = {
        (item.source.value, _normalized(item.identifier))
        for item in response.citations
    }
    expected_labels = {f"{source}:{identifier}" for source, identifier in expected}
    actual_labels = {f"{source}:{identifier}" for source, identifier in actual}
    return _set_grade(GraderKind.CITATION, expected_labels, actual_labels)


def grade_tool_choice(task: EvalTask, response: CandidateResponse) -> Grade:
    expected = _as_set(task.reference.expected_tools)
    actual = {_normalized(call.name) for call in response.tool_calls}
    grade = _set_grade(GraderKind.TOOL_CHOICE, expected, actual)
    allowed = {_normalized(tool) for tool in task.available_tools}
    disallowed = sorted(actual - allowed)
    if disallowed:
        grade.score = 0.0
        grade.passed = False
        grade.details["disallowed"] = disallowed
    return grade


def grade_refusal(task: EvalTask, response: CandidateResponse) -> Grade:
    expected = task.reference.should_refuse
    assert expected is not None
    passed = response.refused is expected
    return Grade(
        grader=GraderKind.REFUSAL,
        score=float(passed),
        passed=passed,
        details={"expected": expected, "actual": response.refused},
    )


GRADERS = {
    GraderKind.EXACT: grade_exact,
    GraderKind.SET: grade_set,
    GraderKind.NUMERIC: grade_numeric,
    GraderKind.CITATION: grade_citations,
    GraderKind.TOOL_CHOICE: grade_tool_choice,
    GraderKind.REFUSAL: grade_refusal,
}


def grade_response(task: EvalTask, response: CandidateResponse) -> list[Grade]:
    """Run the task's graders in declared order."""
    if response.task_id != task.id:
        raise ValueError(
            f"response task_id {response.task_id!r} does not match {task.id!r}"
        )
    return [GRADERS[kind](task, response) for kind in task.graders]

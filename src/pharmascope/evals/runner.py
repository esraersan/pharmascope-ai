"""Evaluation orchestration and aggregate metrics."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from statistics import fmean

from pharmascope.evals.graders import grade_response
from pharmascope.evals.models import (
    AggregateMetrics,
    CandidateResponse,
    EvalTask,
    EvaluationReport,
    Grade,
    TaskResult,
)


def _unique_by_id(items: Iterable[EvalTask]) -> dict[str, EvalTask]:
    indexed: dict[str, EvalTask] = {}
    for item in items:
        if item.id in indexed:
            raise ValueError(f"duplicate task id: {item.id}")
        indexed[item.id] = item
    return indexed


def _responses_by_id(
    responses: Iterable[CandidateResponse],
) -> dict[str, CandidateResponse]:
    indexed: dict[str, CandidateResponse] = {}
    for response in responses:
        if response.task_id in indexed:
            raise ValueError(f"duplicate response for task: {response.task_id}")
        indexed[response.task_id] = response
    return indexed


def aggregate(results: list[TaskResult]) -> AggregateMetrics:
    """Calculate unweighted macro metrics."""
    if not results:
        return AggregateMetrics(
            task_count=0,
            macro_score=0.0,
            task_pass_rate=0.0,
            grader_scores={},
            grader_pass_rates={},
        )

    by_grader: dict[str, list[Grade]] = defaultdict(list)
    for result in results:
        for grade in result.grades:
            by_grader[grade.grader.value].append(grade)

    return AggregateMetrics(
        task_count=len(results),
        macro_score=fmean(result.score for result in results),
        task_pass_rate=fmean(float(result.passed) for result in results),
        grader_scores={
            name: fmean(grade.score for grade in grades)
            for name, grades in sorted(by_grader.items())
        },
        grader_pass_rates={
            name: fmean(float(grade.passed) for grade in grades)
            for name, grades in sorted(by_grader.items())
        },
    )


def evaluate(
    tasks: Iterable[EvalTask],
    responses: Iterable[CandidateResponse],
) -> EvaluationReport:
    """Evaluate exactly one candidate response per task.

    Missing or unknown responses are rejected instead of silently changing the
    denominator.
    """
    task_index = _unique_by_id(tasks)
    response_index = _responses_by_id(responses)
    missing = sorted(task_index.keys() - response_index.keys())
    unknown = sorted(response_index.keys() - task_index.keys())
    if missing or unknown:
        raise ValueError(
            f"response coverage mismatch: missing={missing}, unknown={unknown}"
        )

    results: list[TaskResult] = []
    for task_id, task in task_index.items():
        grades = grade_response(task, response_index[task_id])
        score = fmean(grade.score for grade in grades)
        results.append(
            TaskResult(
                task_id=task_id,
                grades=grades,
                score=score,
                passed=all(grade.passed for grade in grades),
            )
        )
    return EvaluationReport(results=results, metrics=aggregate(results))

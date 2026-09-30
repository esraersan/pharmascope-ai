"""Unit tests for the deterministic evaluation harness."""

import json

import pytest
from pydantic import ValidationError

from pharmascope.evals import (
    CandidateResponse,
    Citation,
    EvalTask,
    Evidence,
    GraderKind,
    ReferenceAnswer,
    Source,
    ToolCall,
    evaluate,
    load_jsonl,
    load_tasks,
    write_jsonl,
)
from pharmascope.evals.__main__ import main
from pharmascope.evals.graders import grade_response


def make_task(
    *graders: GraderKind,
    reference: ReferenceAnswer | None = None,
) -> EvalTask:
    return EvalTask(
        id="pubchem.test",
        source=Source.PUBCHEM,
        prompt="Return the requested structured value.",
        graders=list(graders),
        reference=reference or ReferenceAnswer(exact="Aspirin"),
        available_tools=["pubchem_lookup"],
    )


def test_task_requires_reference_for_each_grader():
    with pytest.raises(ValidationError, match="reference values missing"):
        make_task(GraderKind.NUMERIC)


def test_exact_grader_normalizes_case_and_whitespace():
    task = make_task(GraderKind.EXACT)
    response = CandidateResponse(task_id=task.id, answer="  ASPIRIN\n")

    grade = grade_response(task, response)[0]

    assert grade.passed is True
    assert grade.score == 1.0


def test_set_grader_reports_partial_f1():
    task = make_task(
        GraderKind.SET,
        reference=ReferenceAnswer(set_values=["A", "B", "C"]),
    )
    response = CandidateResponse(task_id=task.id, answer=["A", "B", "D"])

    grade = grade_response(task, response)[0]

    assert grade.passed is False
    assert grade.score == pytest.approx(2 / 3)
    assert grade.details == {"missing": ["c"], "unexpected": ["d"]}


@pytest.mark.parametrize(
    ("answer", "passed"),
    [(180.17, True), ("180.19", False), ("not a number", False)],
)
def test_numeric_grader_uses_declared_tolerance(answer, passed):
    task = make_task(
        GraderKind.NUMERIC,
        reference=ReferenceAnswer(numeric=180.16, absolute_tolerance=0.01),
    )

    grade = grade_response(
        task, CandidateResponse(task_id=task.id, answer=answer)
    )[0]

    assert grade.passed is passed


def test_citation_grader_matches_source_and_identifier():
    task = make_task(
        GraderKind.CITATION,
        reference=ReferenceAnswer(
            evidence=[Evidence(source=Source.PUBCHEM, identifier="2244")]
        ),
    )
    correct = CandidateResponse(
        task_id=task.id,
        citations=[Citation(source=Source.PUBCHEM, identifier="2244")],
    )
    wrong_source = CandidateResponse(
        task_id=task.id,
        citations=[Citation(source=Source.PUBMED, identifier="2244")],
    )

    assert grade_response(task, correct)[0].passed is True
    assert grade_response(task, wrong_source)[0].passed is False


def test_tool_choice_checks_expected_and_allowed_tools():
    task = make_task(
        GraderKind.TOOL_CHOICE,
        reference=ReferenceAnswer(expected_tools=["pubchem_lookup"]),
    )
    response = CandidateResponse(
        task_id=task.id,
        tool_calls=[
            ToolCall(name="pubchem_lookup", arguments={"cid": 2244}),
            ToolCall(name="unlisted_tool"),
        ],
    )

    grade = grade_response(task, response)[0]

    assert grade.passed is False
    assert grade.score == 0.0
    assert grade.details["disallowed"] == ["unlisted_tool"]


@pytest.mark.parametrize(
    ("expected", "actual", "passed"),
    [(True, True, True), (True, False, False), (False, False, True)],
)
def test_refusal_grader(expected, actual, passed):
    task = make_task(
        GraderKind.REFUSAL,
        reference=ReferenceAnswer(should_refuse=expected),
    )
    response = CandidateResponse(
        task_id=task.id,
        refused=actual,
        refusal_reason="Unsupported causal claim" if actual else None,
    )

    assert grade_response(task, response)[0].passed is passed


def test_evaluate_aggregates_task_and_grader_metrics():
    exact_task = make_task(GraderKind.EXACT)
    refusal_task = EvalTask(
        id="faers.refusal",
        source=Source.FAERS,
        prompt="Make an unsupported causal claim.",
        graders=[GraderKind.REFUSAL],
        reference=ReferenceAnswer(should_refuse=True),
    )
    report = evaluate(
        [exact_task, refusal_task],
        [
            CandidateResponse(task_id=exact_task.id, answer="Aspirin"),
            CandidateResponse(task_id=refusal_task.id, refused=False),
        ],
    )

    assert report.metrics.task_count == 2
    assert report.metrics.macro_score == 0.5
    assert report.metrics.task_pass_rate == 0.5
    assert report.metrics.grader_scores == {"exact": 1.0, "refusal": 0.0}


def test_evaluate_rejects_incomplete_response_coverage():
    task = make_task(GraderKind.EXACT)

    with pytest.raises(ValueError, match=r"missing=\['pubchem.test'\]"):
        evaluate([task], [])


def test_jsonl_round_trip(tmp_path):
    path = tmp_path / "responses.jsonl"
    responses = [
        CandidateResponse(
            task_id="pubchem.test",
            answer=180.16,
            tool_calls=[
                ToolCall(name="pubchem_lookup", arguments={"cid": 2244})
            ],
        )
    ]

    write_jsonl(path, responses)

    assert load_jsonl(path, CandidateResponse) == responses


def test_smoke_task_config_spans_all_sources_and_graders():
    tasks = load_tasks("configs/evals/life_science_smoke.json")

    assert {task.source for task in tasks} == set(Source)
    assert {grader for task in tasks for grader in task.graders} == set(GraderKind)
    assert all("smoke" in task.tags for task in tasks)


def test_cli_writes_report_without_calling_a_model(tmp_path):
    tasks_path = tmp_path / "tasks.json"
    responses_path = tmp_path / "responses.jsonl"
    report_path = tmp_path / "report.json"
    tasks_path.write_text(
        json.dumps([make_task(GraderKind.EXACT).model_dump(mode="json")]),
        encoding="utf-8",
    )
    write_jsonl(
        responses_path,
        [CandidateResponse(task_id="pubchem.test", answer="aspirin")],
    )

    exit_code = main(
        [
            "--tasks",
            str(tasks_path),
            "--responses",
            str(responses_path),
            "--report",
            str(report_path),
        ]
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report["metrics"]["task_pass_rate"] == 1.0

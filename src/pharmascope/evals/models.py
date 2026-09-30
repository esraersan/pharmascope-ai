"""Typed schemas for deterministic life-sciences evaluations."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class Source(StrEnum):
    """Scientific data sources represented by the smoke benchmark."""

    PUBMED = "pubmed"
    UNIPROT = "uniprot"
    PDB = "pdb"
    PUBCHEM = "pubchem"
    FAERS = "faers"


class GraderKind(StrEnum):
    """Supported deterministic grading behaviors."""

    EXACT = "exact"
    SET = "set"
    NUMERIC = "numeric"
    CITATION = "citation"
    TOOL_CHOICE = "tool_choice"
    REFUSAL = "refusal"


class Evidence(BaseModel):
    """A reference item that supports an answer."""

    source: Source
    identifier: str = Field(min_length=1)
    locator: str | None = None
    note: str | None = None


class ReferenceAnswer(BaseModel):
    """Ground truth used by one or more graders."""

    exact: str | bool | int | None = None
    set_values: list[str] | None = None
    numeric: float | None = Field(default=None, allow_inf_nan=False)
    absolute_tolerance: float = Field(default=0.0, ge=0.0, allow_inf_nan=False)
    relative_tolerance: float = Field(default=0.0, ge=0.0, allow_inf_nan=False)
    evidence: list[Evidence] = Field(default_factory=list)
    expected_tools: list[str] | None = None
    should_refuse: bool | None = None


class EvalTask(BaseModel):
    """One self-contained evaluation task."""

    id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    source: Source
    prompt: str = Field(min_length=1)
    graders: list[GraderKind] = Field(min_length=1)
    reference: ReferenceAnswer
    available_tools: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_reference_for_graders(self) -> EvalTask:
        required = {
            GraderKind.EXACT: self.reference.exact,
            GraderKind.SET: self.reference.set_values,
            GraderKind.NUMERIC: self.reference.numeric,
            GraderKind.CITATION: self.reference.evidence,
            GraderKind.TOOL_CHOICE: self.reference.expected_tools,
            GraderKind.REFUSAL: self.reference.should_refuse,
        }
        missing = [grader.value for grader in self.graders if required[grader] is None]
        if GraderKind.CITATION in self.graders and not self.reference.evidence:
            missing.append(GraderKind.CITATION.value)
        if missing:
            raise ValueError(
                "reference values missing for graders: " + ", ".join(missing)
            )
        return self


class Citation(BaseModel):
    """Evidence identifier cited by a candidate response."""

    source: Source
    identifier: str = Field(min_length=1)


class ToolCall(BaseModel):
    """One tool invocation captured from an agent trace."""

    name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    returned_identifiers: list[str] = Field(default_factory=list)


class CandidateResponse(BaseModel):
    """Structured model output plus its tool-call trace."""

    task_id: str = Field(min_length=1)
    answer: Any = None
    citations: list[Citation] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    refused: bool = False
    refusal_reason: str | None = None

    @model_validator(mode="after")
    def validate_refusal_reason(self) -> CandidateResponse:
        if self.refused and not self.refusal_reason:
            raise ValueError("refused responses must include refusal_reason")
        return self


class Grade(BaseModel):
    """Result from one grader."""

    grader: GraderKind
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
    details: dict[str, Any] = Field(default_factory=dict)


class TaskResult(BaseModel):
    """All grader results for a single task."""

    task_id: str
    grades: list[Grade]
    score: float = Field(ge=0.0, le=1.0)
    passed: bool


class AggregateMetrics(BaseModel):
    """Macro metrics across evaluated tasks."""

    task_count: int = Field(ge=0)
    macro_score: float = Field(ge=0.0, le=1.0)
    task_pass_rate: float = Field(ge=0.0, le=1.0)
    grader_scores: dict[str, float]
    grader_pass_rates: dict[str, float]


class EvaluationReport(BaseModel):
    """Serializable output of an evaluation run."""

    results: list[TaskResult]
    metrics: AggregateMetrics

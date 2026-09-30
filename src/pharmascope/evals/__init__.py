"""Provider-agnostic evaluation tools for life-sciences agents."""

from pharmascope.evals.io import load_jsonl, load_tasks, write_jsonl
from pharmascope.evals.models import (
    AggregateMetrics,
    CandidateResponse,
    Citation,
    EvalTask,
    EvaluationReport,
    Evidence,
    Grade,
    GraderKind,
    ReferenceAnswer,
    Source,
    TaskResult,
    ToolCall,
)
from pharmascope.evals.runner import aggregate, evaluate

__all__ = [
    "AggregateMetrics",
    "CandidateResponse",
    "Citation",
    "EvalTask",
    "EvaluationReport",
    "Evidence",
    "Grade",
    "GraderKind",
    "ReferenceAnswer",
    "Source",
    "TaskResult",
    "ToolCall",
    "aggregate",
    "evaluate",
    "load_jsonl",
    "load_tasks",
    "write_jsonl",
]

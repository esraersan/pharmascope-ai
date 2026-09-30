# Life-sciences agent evaluations

This package is a small, provider-agnostic harness for grading structured
responses from tool-using scientific agents. It never calls a model, provider,
or scientific API. A caller runs the agent separately and records its answer,
citations, and tool trace.

The bundled tasks are a **smoke benchmark**. They check that an integration can
select a relevant tool and return a few stable fields from PubMed, UniProt,
PDB, PubChem, and FAERS-oriented workflows. Five synthetic tasks cannot
establish scientific reliability, general reasoning quality, safety, or model
superiority. Do not publish their scores as evidence of model quality.

## Data model

`EvalTask` contains:

- a stable task ID, source, prompt, and tags;
- the tools exposed to the agent;
- an explicit list of deterministic graders;
- a reference answer and supporting evidence.

`CandidateResponse` contains:

- the corresponding task ID and structured answer;
- citations as source/identifier pairs;
- ordered tool calls with arguments and returned identifiers;
- an explicit refusal flag and reason.

This separation keeps model execution outside the evaluator. It also avoids
inventing traces: only observed candidate output should be serialized.

## Grading

The harness supports:

- `exact`: case-folded, whitespace-normalized scalar equality;
- `set`: order-independent normalized equality, with F1 as partial credit;
- `numeric`: absolute and/or relative tolerance;
- `citation`: exact source/identifier set matching, with F1 partial credit;
- `tool_choice`: exact unique tool-name set matching, plus rejection of tools
  not exposed by the task;
- `refusal`: equality with the expected refusal decision.

A task score is the unweighted mean of its grader scores. A task passes only
when every declared grader passes. `macro_score` and `task_pass_rate` are
unweighted across tasks. Per-grader means and pass rates are also reported.
Missing, duplicate, or unknown responses cause an error so the denominator
cannot change silently.

The citation grader verifies identifiers against the task's curated evidence;
it does not independently establish that a source supports every sentence.
The tool-choice grader checks selected tool names, not argument semantics or
call order. More demanding benchmarks should add domain-reviewed tasks and
purpose-built graders rather than treating these checks as scientific
validation.

## File formats

Task sets can be a JSON array or JSONL, with one `EvalTask` per line. Candidate
responses are JSONL, one `CandidateResponse` per line. Reports are JSON; task
results can optionally be emitted as JSONL.

Example candidate response:

```json
{"task_id":"pubchem.aspirin-molecular-weight","answer":180.16,"citations":[{"source":"pubchem","identifier":"2244"}],"tool_calls":[{"name":"pubchem_lookup","arguments":{"cid":2244},"returned_identifiers":["2244"]}]}
```

The smoke tasks are in
`configs/evals/life_science_smoke.json`. They intentionally do not include
candidate responses or model scores.

## Run

With a JSONL file containing one real response for every task:

```bash
python -m pharmascope.evals \
  --tasks configs/evals/life_science_smoke.json \
  --responses path/to/responses.jsonl \
  --report path/to/report.json \
  --results-jsonl path/to/results.jsonl
```

Run the unit tests with:

```bash
pytest tests/unit/test_evals.py
```

Both commands use the project's existing dependencies. Evaluation is local,
deterministic, and offline.

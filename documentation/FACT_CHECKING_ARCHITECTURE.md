# Fact-checking architecture

## Evidence contract

The fact checker accepts claims from workflow state or asks the configured LLM
to extract individual factual claims from retrieved evidence. Evidence is
collected from normalized web/academic sources, cited document passages, and,
when configured, user-scoped RAG retrieval.

Each evidence item retains a stable reference such as a source URL, title,
document citation, or chunk ID. Only evidence supplied by the workflow can
support a result; an LLM response by itself is never treated as evidence.

## Verification statuses

- `supported`: relevant evidence is attributed and the evaluator finds direct
  support.
- `contradicted`: relevant evidence is attributed and the evaluator finds a
  contradiction.
- `insufficient_evidence`: no relevant evidence exists, evidence references
  are missing, or the evaluator cannot justify either conclusion.

Structured Pydantic responses validate status, explanation, confidence, and
evidence references. Unsupported references are discarded, and a model that
returns support without an attributed reference is downgraded to
`insufficient_evidence`.

## Persistence and safety

Verified claims retain claim text, status, explanation, confidence, and
references in the existing `VerifiedClaim` model. Research-run ownership is
validated before persistence. Agent execution records contain bounded
summaries, not source contents or credentials.

Provider failures and invalid structured responses are surfaced as explicit
workflow errors. They do not generate placeholder claims.

## Testing

Tests cover supported claims, unattributed model responses, empty evidence,
structured planner output, document citations, dataset analysis, routing, and
workflow state sharing. Providers are mocked, so no paid API access is needed.

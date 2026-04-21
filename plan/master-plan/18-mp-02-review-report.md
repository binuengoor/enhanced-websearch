# MP-02 Review Report

Reviewed branch `mp-02-planning-review` against `plan/master-plan/17-mp-02-planning-routing-foundation-test-plan.md`.

## Verdict

MP-02 is close, but not fully aligned with the test plan yet.

## What passed

- `RoutingDecision` and `ResearchPlan` are now separate structured schemas and are attached to diagnostics.
- `execute_search()` validates both planner outputs through Pydantic before use.
- `/search` remains on the fast path: `execute_perplexity_search()` still constructs internal `SearchRequest(mode="fast")` requests and does not depend on the new routing decision path.
- The `/search` path still has heuristic fallback behavior for its quick profile selection when `compiler.choose_search_profile()` is unavailable or disabled.
- Runtime remains bounded in the orchestrator: only `research` can iterate beyond one cycle, and iteration count is capped by `min(req.max_iterations, mode_budget.max_queries)`.
- The `decision_source` scaffold is present and currently behaves as expected for this milestone: `heuristic` for `auto`, `override` for explicit mode, with no active LLM routing path wired yet.
- Syntax check passed: `python3 -m compileall app` succeeded.

## Findings

### 1. Research plan bounding is not enforced by the plan schema itself

Status: blocking against the test plan's bounded-plan acceptance language.

Details:

- `ResearchPlan.max_iterations` is recorded but not normalized against `mode_budget.max_queries` inside `build_research_plan()` or schema validation.
- `ResearchPlan.steps` has no explicit maximum length or schema-level bound.
- The orchestrator does enforce execution bounds, so runtime is still protected in practice.
- However, the test plan asks for planner output to be bounded in shape and execution consequences, and for explicit maximum steps/subqueries. The current implementation provides the fields but not schema-level enforcement.

Relevant code:

- `app/models/contracts.py:29`
- `app/services/planner.py:81`
- `app/services/orchestrator.py:80`

## Notes

- `choose_mode()` still works via `build_route_decision()` and preserves the existing heuristic behavior.
- `/search` has not become planner-dependent for route selection, which matches the non-goal requirements.
- There is no explicit fallback-reason field for `/research` planner routing/planning because the current implementation is heuristic-first rather than planner-optional. For this milestone that is acceptable scaffolding, but future LLM planner work should preserve a visible fallback indicator if heuristics are used after planner failure.
- The schemas are intentionally minimal and do not yet include richer fields suggested by the test plan such as `reason_codes`, `confidence`, `fallback_used`, `breadth`, `needs_recency_check`, or `plan_source`.

## Overall assessment

The implementation satisfies most of the MP-02 foundation goals:

- separate routing and planning contracts
- auditable diagnostics wiring
- preserved `/search` fast-path behavior
- bounded execution loop behavior

The remaining mismatch is that the research-plan contract is descriptive rather than strictly bounded/normalized at the schema level, so I would not mark MP-02 fully complete until that is tightened.

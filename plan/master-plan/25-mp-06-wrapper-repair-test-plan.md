# MP-06 Wrapper Repair Test Plan

This artifact defines how to validate the MP-06 goal of repairing the Open WebUI wrapper so it behaves like a thin adapter over stable backend semantics rather than a second implementation of product logic.

It is intentionally test-focused.
It does not authorize backend feature changes, wrapper-owned orchestration, or wrapper-specific semantics that diverge from the canonical backend contract.

## Scope

This plan covers:

- wrapper contract parity with backend `/search`, `/research`, `/fetch`, and `/extract`
- parity checks against MCP behavior where MCP already performs canonical contract normalization
- recency handling validation, especially multi-unit windows such as `3 months`
- wrapper response shape and structure quality at the Open WebUI tool boundary
- wrapper progress and status behavior during long-running research after MP-05 SSE work
- regression protection that the wrapper remains thin and does not own backend logic
- success criteria for deciding whether "wrapper repair works"

This plan does not cover:

- backend orchestration redesign already owned by earlier milestones
- provider tuning, fallback policy changes, or routing strategy changes
- benchmark/scoring work intended for later milestones
- broad Open WebUI UX redesign outside the tool contract and status behavior

## Baseline references

Use these repo artifacts as the source of truth while running this plan:

- `plan/master-plan/02-recommended-execution-order.md`
- `plan/master-plan/05-open-webui-wrapper-diagnosis.md`
- `plan/master-plan/10-master-backlog.md`
- `plan/master-plan/11-dev-workstreams.md`
- `plan/master-plan/12-test-workstreams.md`
- `plan/master-plan/23-mp-05-progress-streaming-test-plan.md`

Current code paths relevant to this test plan:

- `enhanced-websearch/enhanced_websearch.py`
- `app/api/routes.py`
- `app/mcp_server.py`
- `app/models/contracts.py`
- `README.md`

## MP-06 acceptance anchor

MP-06 is only complete when all of the following are true:

- wrapper requests preserve backend meaning rather than dropping or inventing fields
- wrapper behavior matches backend and MCP semantics for quick search and research inputs that should be equivalent
- multi-unit recency requests are normalized into canonical backend fields correctly
- wrapper progress reflects real backend progress or an explicitly bounded adapter over backend progress, not synthetic keepalive timers pretending to know state
- wrapper returns a response shape that is stable, inspectable, and consistent with backend payload structure expectations in Open WebUI
- wrapper does not duplicate orchestration, fallback, synthesis, routing, or health-inference logic
- long-running research no longer feels hung while still remaining faithful to backend stage truth

## Current implementation observations to validate

These observations come from the current repository state and should be re-checked once MP-06 implementation exists:

- the wrapper currently exposes four tools and posts to `/search`, `/research`, `/fetch`, and `/extract`
- `concise_search(...)` forwards `search_recency_amount` directly even though the `/search` request contract does not define that field
- MCP already performs recency normalization before calling `/search`, so wrapper and MCP are currently not equivalent for multi-unit recency windows
- wrapper methods currently end with `json.dumps(response, ensure_ascii=False)`, which makes the tool boundary more string-oriented than MCP
- wrapper progress is currently local timer-based status emission every 10 seconds, not backend stage-driven progress
- MP-05 introduced backend SSE streaming, so MP-06 should validate wrapper consumption or rendering of that stable backend progress model rather than inventing a new one

## Proposed validation model

Use a layered test strategy:

1. contract inspection for wrapper tool signatures and emitted request payloads
2. deterministic normalization checks for recency and mode mapping
3. comparative checks between wrapper, MCP, and direct backend invocation
4. manual Open WebUI validation for response rendering and long-run status behavior
5. regression checks that wrapper code remains thin and free of backend-owned logic

Prefer deterministic fixtures or request capture where possible. Use live upstream/provider runs only for final acceptance and operator-level confirmation.

## Test matrix

Validate these path combinations at minimum:

- concise search with no recency filter
- concise search with one-unit recency filter such as `1 week`
- concise search with multi-unit recency filter such as `3 months`
- research search with short-running query
- research search with long-running query that emits multiple backend progress stages
- fetch and extract passthrough sanity checks
- backend error path and timeout path surfaced through the wrapper

For each path, compare:

- wrapper outbound request shape
- backend-visible request shape if observable through logs or instrumentation
- final response structure
- progress/status behavior while running
- user-visible error structure on failure

## Contract parity validation

### Objective

Prove that the wrapper preserves the canonical backend contract and matches MCP where MCP exists only to normalize inputs into backend-supported fields.

### Method

Use one or more of the following:

- unit tests around wrapper payload construction
- request capture against a local stub server that records JSON request bodies
- side-by-side invocation of wrapper and MCP using equivalent user inputs
- direct comparison to backend request models in `app/models/contracts.py`

### Required checks

- `concise_search(...)` sends only backend-supported `/search` fields after wrapper normalization
- `research_search(...)` sends only backend-supported `/research` fields and does not silently add semantics not present in backend contracts
- `fetch_page(...)` and `extract_page_structure(...)` remain straightforward pass-through adapters
- wrapper mode mapping does not mutate the meaning of `auto`, `web`, `academic`, `sec`, `source_mode`, or `depth`
- any client tag or metadata added by the wrapper is observational only and does not alter backend decision logic

### Evidence to capture

- example recorded request payloads for each tool path
- explicit comparison table of wrapper input vs backend payload vs expected canonical payload
- note of any intentional wrapper-only adaptations and why they are required for parity

## Recency handling validation

### Objective

Prove that user-facing recency requests such as `3 months` survive the wrapper path with the same effective meaning as MCP and direct backend canonical inputs.

### Core risk

The diagnosis artifact identifies that the current wrapper forwards `search_recency_amount`, which `/search` ignores. This collapses requests like `3 months` into the one-unit bucket for `month`.

### Required cases

Run at least these cases through wrapper, MCP, and direct API comparison:

- `search_recency_filter=none`, amount omitted or defaulted
- `1 day`
- `3 months`
- `2 years`
- invalid amount `0` or negative amount if user input can reach wrapper validation

### Expected validation outcomes

- one-unit windows keep their expected meaning without unnecessary canonical-field expansion
- multi-unit windows are converted into canonical backend fields such as `search_after_date_filter` when that is how backend semantics are expressed
- wrapper does not send unsupported fields that backend silently drops
- invalid amounts are either clamped or rejected consistently with the intended canonical contract, and behavior matches MCP expectations

### Suggested evidence

- captured outbound JSON for each case
- computed canonical date threshold or backend field mapping for each multi-unit case
- result comparison showing wrapper and MCP are aligned in effective filtering behavior

## Response shape and structure quality validation

### Objective

Prove that the wrapper returns payloads that are easy for Open WebUI to interpret and that preserve backend response structure instead of degrading it into an opaque blob.

### Required checks

- successful concise search responses preserve important top-level fields and nested result structure
- successful research responses preserve answer, citations, summaries, metadata, and any debug/legacy exclusions expected by backend contract
- error responses preserve enough structure to distinguish HTTP errors, timeout errors, and backend-declared application errors
- partial-success or degraded backend responses remain parseable and do not lose typed fields through wrapper transformation
- if the wrapper must return text for Open WebUI compatibility, verify that the text is valid JSON matching the backend payload shape exactly and does not wrap the payload again or discard fields

### Manual UI checks

In Open WebUI, verify:

- tool output renders predictably for concise search and research
- citations or structured sections are still recoverable from the wrapper response
- large responses do not become malformed or truncated unexpectedly at the wrapper boundary

### Suggested evidence

- saved example payloads from concise search, research, and one error case
- a short note describing whether the wrapper now returns native objects, JSON text, or another Open WebUI-compatible structure, and why that boundary is acceptable

## Progress and status handling validation

### Objective

Prove that long-running wrapper requests surface useful, truthful progress derived from backend work rather than synthetic timer messages.

### Preconditions

- MP-05 backend progress streaming is already considered stable enough to consume
- at least one long-running research query exists that emits multiple backend stages

### Required checks

- wrapper status updates correspond to real backend stages or backend-driven progress events
- stage ordering seen in Open WebUI is consistent with the backend SSE stream ordering guarantees validated in MP-05
- status updates stop cleanly on completion, error, or cancellation
- long runs no longer emit generic repeating messages that imply activity without reflecting backend state
- quick paths do not regress into noisy progress spam when no meaningful progress stream exists

### Resilience checks

- backend emits progress then completes successfully
- backend emits progress then errors
- client disconnects or cancels during a long-running request if that behavior is observable in the wrapper environment
- backend emits no intermediate progress for a short request and wrapper remains quiet or minimally informative

### Suggested evidence

- timestamped sample of Open WebUI status messages for a long-running research run
- corresponding backend SSE event sample for the same run
- comparison note showing wrapper-visible status is a rendering of backend truth, not a second state machine

## Thin-wrapper regression validation

### Objective

Prove that the wrapper does not own backend logic and stays within its intended adapter role.

### Code review checklist

Inspect `enhanced-websearch/enhanced_websearch.py` and related wrapper docs for signs of forbidden ownership.

Fail MP-06 if the wrapper contains new logic for any of the following:

- provider routing decisions
- search vs research orchestration policy beyond calling the selected backend endpoint
- fallback chains or retries that change semantic behavior relative to backend
- synthesis, citation assembly, reranking, or evidence selection logic
- synthetic health inference from timers or guessed backend state
- duplicate schema definitions that can drift from backend contracts without a clear compatibility reason

### Acceptable wrapper ownership

Allow only narrowly-scoped adaptation such as:

- Open WebUI-friendly tool names and argument schema
- authentication/header forwarding
- canonical request normalization required to preserve backend semantics
- translation of backend progress events into Open WebUI status emissions
- minimal error wrapping needed for tool-runtime compatibility

### Suggested evidence

- brief review notes identifying any newly added logic blocks and whether they are adapter-only or semantically risky
- explicit statement that backend remains canonical owner of orchestration semantics

## Error handling validation

Validate at least these failure modes:

- backend returns HTTP 4xx with structured body
- backend returns HTTP 5xx with structured or unstructured body
- network failure to backend service
- timeout during long-running request
- malformed or unexpected backend payload if a stub can simulate it

Pass criteria:

- wrapper surfaces actionable error information without inventing backend facts
- wrapper does not emit misleading completion statuses after failures
- Open WebUI user can distinguish unavailable backend from normal empty-result cases

## Manual acceptance runbook

Run this acceptance flow after automated checks pass:

1. start the backend build that includes MP-05 progress streaming and the MP-06 wrapper repair
2. invoke concise search in Open WebUI with a normal query and verify correct results
3. invoke concise search with `3 months` recency and verify backend-visible/captured payload uses canonical semantics rather than dropped fields
4. invoke research search with a long-running query and observe multiple truthful status updates
5. compare the final wrapper result to the corresponding direct API or MCP result for the same query class
6. exercise one backend failure path and verify user-visible error clarity

## Success criteria for "wrapper repair works"

Decide that MP-06 passes only when all of the following are true:

- wrapper quick-search invocation matches backend semantics for normal and recency-constrained searches
- multi-unit recency windows such as `3 months` map correctly and no longer collapse to one-unit buckets
- research invocation remains thin and returns backend-shaped data without losing key structure
- long-running research shows useful backend-driven status in Open WebUI and no longer feels hung
- wrapper error handling is truthful and operationally useful
- code inspection shows no new backend-owned logic has migrated into the wrapper
- wrapper behavior is consistent with direct API and MCP expectations for equivalent requests

## Exit artifacts

Capture these artifacts before marking MP-06 complete:

- automated test results or recorded manual checks for wrapper quick search, research, progress, and errors
- request/response examples covering at least one multi-unit recency case and one long-running research case
- short code review notes confirming the wrapper remains thin
- any follow-up gaps that should roll into post-MP-06 cleanup instead of blocking acceptance

## Notes

This plan intentionally treats backend semantics as canonical.
The wrapper succeeds only if it becomes a boring adapter over those semantics, not a competing implementation.
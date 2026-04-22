# Pre-Push QA Plan

Status: Draft for execution
Scope: MP-00 through MP-09
Target branch: `main`
Purpose: provide a single actionable pre-push QA plan that testing subagents can execute before shipping changes across the implemented milestone stack.

## Test execution notes

- Use this plan for review and validation only; do not change code while executing test cases unless a separate fix task is opened.
- Record evidence for each case: command used, request payload, response summary, and pass/fail outcome.
- Prefer the canonical public surfaces first: `POST /search`, `POST /research`, `GET /metrics`, `GET /runs/recent`, `POST /research/export`, `GET /health`, and `GET /config/effective`.
- When a case needs a failure scenario, induce it with configuration or an intentionally unavailable upstream, not by editing code.
- For API checks, capture both HTTP status and important response fields.
- For artifact checks, verify both existence and readable content.

## Code Quality

### TC-01 - Dead and unused imports
What to test:
Confirm the codebase does not contain dead or unused imports introduced across MP-00 through MP-09.

How to test:
Run a static review pass across `app/` and `tests/` using a linter or targeted search. Check for imports that are never referenced, duplicate imports, or imports left from removed milestone work. Focus on `app/api/routes.py`, `app/services/`, `app/providers/`, and `app/mcp_server.py`.

Expected result:
No unused imports remain, or every apparent exception is justified by framework/runtime behavior and documented in the review notes.

### TC-02 - Dead and unused functions or methods
What to test:
Confirm there are no orphaned functions, helper methods, or endpoint support routines that are no longer reachable after the `/search` and `/research` split and MP-09 additions.

How to test:
Inspect the call graph manually or with search tools. Look for functions defined but never called, especially in orchestration, report export, run history, router health, and MCP wrapper layers. Cross-check route registration against available handlers.

Expected result:
All functions and methods are referenced intentionally, or any compatibility-only code paths are clearly justified and not accidental leftovers.

### TC-03 - Dead and unused variables
What to test:
Confirm there are no variables, intermediate values, or configuration fields assigned but never used.

How to test:
Run a linter or targeted source review for assigned-but-unused locals, stale constants, and no-op branches. Focus on request adaptation, progress streaming, metrics assembly, and export paths.

Expected result:
No unused variables remain in active code paths.

### TC-04 - Sync work inside async request paths
What to test:
Identify blocking or synchronous operations inside async API routes or async orchestration paths that can harm latency under load.

How to test:
Review `app/api/routes.py` plus downstream services used by `/search`, `/research`, `/fetch`, `/extract`, `/metrics`, `/runs/recent`, and `/research/export`. Check for blocking file I/O, blocking HTTP calls, blocking subprocess usage, or CPU-heavy loops executed directly in async functions without offloading.

Expected result:
Async request paths avoid obvious blocking work, or any unavoidable synchronous operation is bounded and justified.

### TC-05 - Query and provider performance anti-patterns
What to test:
Confirm routing and retrieval logic do not contain avoidable N+1 provider calls, redundant page fetches, unbounded iteration, or missing retry bounds.

How to test:
Review planner, orchestrator, fetch/extract, and provider routing logic. Verify iteration limits are enforced from request/config, provider fallback is bounded, and deep or quality flows do not expand indefinitely. Confirm caches and dedupe are used where intended.

Expected result:
Provider attempts, fetch loops, and follow-up cycles are bounded and consistent with configured budgets.

### TC-06 - Missing timeout coverage
What to test:
Confirm all external calls and optional integrations have meaningful timeout handling.

How to test:
Inspect provider adapters, fetch/extract services, Vane integration, LiteLLM calls, and any export-related I/O for timeout configuration or bounded waits. Verify no external network path depends on an implicit infinite timeout.

Expected result:
All upstream-facing operations have explicit or centrally enforced timeouts appropriate to their mode.

### TC-07 - Error handling completeness
What to test:
Confirm request handlers and service paths return meaningful errors and do not hide failures.

How to test:
Review for bare `except:` blocks, swallowed exceptions, missing re-raise behavior, or generic error strings that would make diagnosis hard. Check API routes, orchestrator failure recording, auto-export warnings, and SSE error emission.

Expected result:
No bare `except:` blocks exist; failures are surfaced with useful messages and consistent status handling.

### TC-08 - Logging quality on failure paths
What to test:
Confirm important failure paths are logged with enough detail to debug provider failures, export failures, and routing degradation.

How to test:
Review logging calls in orchestrator, provider router, report exporter, and app startup. Verify logs include cause and context without leaking secrets.

Expected result:
Operationally important failures produce useful logs, and logs avoid secret exposure.

### TC-09 - Security basics and secrets hygiene
What to test:
Confirm no hardcoded credentials or unsafe secret handling exist.

How to test:
Search the repo for API keys, bearer tokens, sample secrets, and direct secret literals. Inspect config loading and `GET /config/effective` redaction behavior. Verify docs and code keep secrets in env vars rather than committed files.

Expected result:
No hardcoded real secrets are present, and effective config output redacts secret values.

### TC-10 - Input validation and safe file paths
What to test:
Confirm request models and export logic validate user input and avoid unsafe path handling.

How to test:
Review request contracts and route handlers for query/depth/mode validation, limit bounds, and typed request payloads. Inspect report export path creation to ensure output stays under the intended reports directory and is not user-path-injectable.

Expected result:
Inputs are validated at the schema or route layer, and report export writes only to safe local artifact paths.

### TC-11 - Consistency of patterns and naming
What to test:
Confirm the codebase uses consistent terminology and patterns after the endpoint split and depth-mode transition.

How to test:
Review docs, routes, MCP tool naming, diagnostics fields, and response semantics. Check for inconsistent use of `quick`, `fast`, `research`, `deep`, `balanced`, and `quality`, especially where public contract and internal compatibility differ.

Expected result:
Public surfaces consistently present canonical semantics, and any compatibility vocabulary is intentional and documented.

## API Endpoints

### TC-12 - `/search` happy path
What to test:
Verify `POST /search` returns concise, Perplexity-style search results for a normal query.

How to test:
Send a valid request with a straightforward query and a small `max_results` value. Confirm HTTP 200, response includes `id` and `results`, and each result includes `title`, `url`, and `snippet`.

Expected result:
The endpoint returns a valid concise result set with no long-form research-only fields required.

### TC-13 - `/search` upstream failure handling
What to test:
Verify `POST /search` degrades gracefully when the preferred upstream provider fails.

How to test:
Temporarily disable or break the preferred provider via runtime configuration or test environment, then send a valid search request. Observe whether fallback occurs, and if all providers fail, capture the returned error and run-history entry.

Expected result:
The service either falls back successfully or returns a meaningful failure without crashing, and the failure is observable in diagnostics/history.

### TC-14 - `/search` empty result behavior
What to test:
Verify `POST /search` handles a no-result query cleanly.

How to test:
Send a query that should reasonably produce zero results or use a constrained filter combination likely to empty the set. Confirm the response shape remains valid and does not error solely because zero results were found.

Expected result:
HTTP 200 with an empty `results` list or equivalent valid empty response behavior, with no malformed output.

### TC-15 - `/search` mode variations and filters
What to test:
Verify supported search knobs change behavior without breaking the contract.

How to test:
Execute multiple `POST /search` requests varying supported fields such as `search_mode`, recency filters, recency amount, country, and domain/date filters. Compare response shape and confirm the endpoint still behaves as a fast retrieval path.

Expected result:
Requests succeed with supported parameter combinations, mode/filter knobs are accepted, and the response contract remains stable.

### TC-16 - `/research` happy path
What to test:
Verify `POST /research` returns a grounded long-form research response for a normal research query.

How to test:
Send a valid research payload with `depth=balanced`. Confirm HTTP 200 and verify the response contains a structured answer with long-form fields such as summary/findings/citations/sources/diagnostics/timings.

Expected result:
The endpoint returns a complete research response with citations and diagnostics suitable for long-form use.

### TC-17 - `/research` upstream failure handling
What to test:
Verify `POST /research` handles provider or synthesis failures cleanly.

How to test:
Induce a provider outage or invalid upstream dependency state, then submit a research request. Capture HTTP status or degraded response behavior, and verify recent-run history records the failure.

Expected result:
The service returns a meaningful failure or bounded degraded result, records the failed run, and does not hang indefinitely.

### TC-18 - `/research` with Vane disabled
What to test:
Verify `POST /research` still succeeds when Vane is turned off.

How to test:
Run the service with `VANE_ENABLED` disabled or equivalent config disabled, then issue a research request. Compare output shape against the normal happy path.

Expected result:
Research still succeeds through the retrieval-first path, with no dependency on Vane being enabled.

### TC-19 - `/research` depth modes
What to test:
Verify public research depth modes behave correctly, including compatibility handling.

How to test:
Run `POST /research` with `depth=balanced`, `depth=quality`, and compatibility `depth=quick`. Compare timing, breadth, or diagnostics where visible, and confirm all accepted depths are handled without schema failure.

Expected result:
`balanced` and `quality` work as supported public depths, `quick` is accepted for compatibility, and responses remain structurally valid.

### TC-20 - `/research` SSE progress streaming
What to test:
Verify progress streaming works for long-form research.

How to test:
Call `POST /research?stream=true` with a valid research request and inspect the event stream. Confirm progress events arrive in order and terminal output includes either a `result` event or an `error` event.

Expected result:
The stream emits valid SSE events with meaningful stage updates and a clean terminal event.

### TC-21 - `/metrics` response completeness
What to test:
Verify `GET /metrics` returns the canonical observability snapshot.

How to test:
Call `GET /metrics` after several successful and failed requests. Confirm the response includes cache stats, provider summary, and recent request summary with total/success/failed counts.

Expected result:
The response contains the expected metrics categories and reflects recent activity accurately.

### TC-22 - `/runs/recent` after mixed request traffic
What to test:
Verify `GET /runs/recent` shows newest-first bounded debugging history after different request types.

How to test:
Execute a mix of successful `/search`, successful `/research`, failed `/search`, and failed `/research` requests. Then call `GET /runs/recent` with default and custom `limit` values.

Expected result:
Entries are newest-first, capped by limit/history bounds, and include endpoint, query, mode, outcome, and capped warnings/errors as documented.

### TC-23 - `/research/export` manual export
What to test:
Verify manual report export works for a completed research response.

How to test:
First obtain a successful `/research` response. Submit that response to `POST /research/export`. Verify the returned export metadata and inspect the created report directory under `artifacts/reports/`.

Expected result:
A new report directory is created containing readable `report.md` and `report.yaml` artifacts.

### TC-24 - `/research` auto-export behavior
What to test:
Verify automatic report export triggers only on successful research completion when enabled.

How to test:
Run with `service.auto_export_research=true`. Submit one successful research request and one failing research request. Inspect `artifacts/reports/` and compare report count before and after.

Expected result:
A report is created for the successful research request only; failed research requests do not create auto-export artifacts.

### TC-25 - `/health`
What to test:
Verify liveness endpoint behavior.

How to test:
Call `GET /health` on a running service.

Expected result:
HTTP 200 with a simple healthy status payload.

### TC-26 - `/config/effective`
What to test:
Verify effective config output is available for debugging and remains non-secret.

How to test:
Call `GET /config/effective` with representative runtime configuration loaded. Inspect the payload for expected sections and redaction behavior.

Expected result:
The endpoint returns effective config data useful for debugging, with secrets removed or redacted.

### TC-27 - MCP tool `search`
What to test:
Verify the MCP `search` tool responds correctly and mirrors concise search behavior.

How to test:
Invoke the MCP tool with a valid query and supported knobs. Confirm the tool returns a successful structured result and that the response shape is aligned with the concise search contract.

Expected result:
The tool responds successfully with concise search data and no unexpected schema drift.

### TC-28 - MCP tool `research`
What to test:
Verify the MCP `research` tool responds correctly for long-form research.

How to test:
Invoke the MCP tool with a valid research query and typical depth/source arguments. Inspect the structured result.

Expected result:
The tool returns a valid long-form research response aligned with the HTTP research surface.

### TC-29 - MCP tool `fetch_page`
What to test:
Verify the MCP `fetch_page` tool can fetch a page successfully.

How to test:
Invoke the tool with a known accessible URL.

Expected result:
The tool returns fetched content or structured fetch output without transport/schema errors.

### TC-30 - MCP tool `extract_page_structure`
What to test:
Verify the MCP `extract_page_structure` tool returns structured page extraction data.

How to test:
Invoke the tool with a known accessible URL containing clear page structure.

Expected result:
The tool returns extraction metadata/content structure successfully.

### TC-31 - MCP tool `health_check`
What to test:
Verify the MCP `health_check` tool reflects service liveness.

How to test:
Invoke the MCP tool against a running service.

Expected result:
The tool returns a healthy status consistent with `GET /health`.

### TC-32 - MCP tool `providers_health`
What to test:
Verify the MCP `providers_health` tool exposes provider-level state.

How to test:
Invoke the tool before and after inducing a provider failure/cooldown scenario.

Expected result:
The tool returns provider entries showing enabled state and health/cooldown details consistent with the HTTP provider health surface.

### TC-33 - MCP tool `service_metrics`
What to test:
Verify the MCP `service_metrics` tool mirrors the canonical `/metrics` response.

How to test:
Invoke the MCP tool after several requests and compare the result shape and values against `GET /metrics`.

Expected result:
The tool returns the same core metrics view as `/metrics` with no conflicting semantics.

## Integration

### TC-34 - Run history records both success and failure
What to test:
Verify recent-run history captures both successful and failed request outcomes across endpoint types.

How to test:
Generate at least one successful `/search`, one failed `/search`, one successful `/research`, and one failed `/research`. Inspect `GET /runs/recent`.

Expected result:
History includes both success and failure entries with correct endpoint, mode, and error/warning summaries.

### TC-35 - Auto-export only on successful `/research`
What to test:
Verify integration between research completion and auto-export is gated correctly.

How to test:
With auto-export enabled, execute one successful research request, one validation failure, and one upstream failure. Inspect export directory creation and logs.

Expected result:
Only successful completed research requests create export artifacts; failures do not.

### TC-36 - Report artifacts are readable and complete
What to test:
Verify exported report artifacts are useful and complete for local-first consumption.

How to test:
Open the generated `report.md` and `report.yaml` from a successful export. Check readability, basic structure, key answer sections, and citation/source presence where expected.

Expected result:
Both files are readable, parseable by humans/tools, and contain a complete enough representation of the research result.

### TC-37 - Metrics reflect provider health changes
What to test:
Verify provider health degradation and recovery are surfaced through metrics after runtime changes.

How to test:
Capture baseline `/metrics`, then induce provider failure or cooldown with repeated failed requests, and query `/metrics` again. If feasible, allow recovery and query once more.

Expected result:
Provider summary changes in a way that reflects health degradation/cooldown and later recovery when conditions improve.

### TC-38 - `/metrics` and `/runs/recent` stay consistent together
What to test:
Verify aggregate request counts in `/metrics` align logically with detailed recent history samples.

How to test:
Generate a small controlled sequence of requests and compare `/metrics` totals/success/failed against the entries shown in `/runs/recent`.

Expected result:
The aggregate counters and recent history tell a consistent story for the same test window.

### TC-39 - Streaming, history, and export interaction
What to test:
Verify a streamed `/research` request still participates correctly in run history and export behavior.

How to test:
Execute a successful `POST /research?stream=true` request with auto-export enabled, then inspect `/runs/recent` and `artifacts/reports/`.

Expected result:
The streamed request records as a successful research run and produces export artifacts just like a non-streamed successful request.

## Deployment

### TC-40 - Docker build succeeds
What to test:
Verify the project builds successfully into a container image from the current branch.

How to test:
Run the documented Docker build or compose build flow from a clean working tree state and capture success/failure.

Expected result:
The image builds successfully without requiring ad hoc source changes.

### TC-41 - Container starts with `config.yaml`
What to test:
Verify the container starts correctly using the intended config file path and serves the app.

How to test:
Start the container with the shipped configuration arrangement. Confirm startup completes and basic endpoints such as `GET /health` respond.

Expected result:
The container boots successfully with `config/config.yaml` and exposes the service.

### TC-42 - Compose bind mount for reports directory
What to test:
Verify the compose configuration correctly bind-mounts the reports directory for local artifact persistence.

How to test:
Start the service through `docker compose`, execute a successful research export, then verify the created report directory is visible on the host in the bind-mounted path.

Expected result:
Generated report artifacts are accessible from the host through the compose-mounted reports directory.

## Exit criteria

- All critical API endpoint cases pass, especially `/search`, `/research`, `/metrics`, `/runs/recent`, and `/research/export`.
- All seven MCP tools respond successfully and match their intended HTTP semantics.
- No blocking code quality issues are found in dead code, timeout handling, security basics, error handling, or consistency.
- Integration checks confirm success/failure history capture, success-only auto-export, readable report artifacts, and provider health visibility.
- Deployment checks confirm Docker build, container startup with config, and compose report bind mount behavior.
- Any failed non-blocking case is documented with severity, reproduction steps, and milestone relevance before push approval.

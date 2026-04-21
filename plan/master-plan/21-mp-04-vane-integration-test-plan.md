# MP-04 Vane Integration Test Plan

This artifact defines how to validate the MP-04 goal of repairing backend Vane integration without expanding product scope.

It focuses on proving that the backend `POST /research` path:

- actually sends the intended request to Vane
- parses the returned Vane payload correctly
- falls back safely when Vane is slow or unavailable
- no longer hides successful Vane output behind snippet-style research responses

It does not redefine `/research` semantics, authorize new product behavior, or make Vane mandatory for acceptable backend operation.

## Scope

This plan covers:

- MP-04 acceptance validation for backend Vane integration
- request-shape parity between direct Vane and backend-driven Vane
- response parsing validation for the current Vane API shape
- timeout and error fallback behavior for `research` and `deep`-style execution
- comparison of direct Vane versus backend `/research` behavior for the same input

This plan does not cover:

- direct Vane model benchmarking beyond the known-good baseline
- final product decisions about making Vane primary, optional, or disabled by default
- SSE progress work planned for MP-05
- broad research-answer quality checks already covered by MP-03 unless they are needed to prove Vane output is surfaced

## Baseline references

Use these repo artifacts as the source of truth while running this plan:

- `plan/master-plan/07-known-good-direct-vane-config.md`
- `plan/master-plan/05-open-webui-wrapper-diagnosis.md`
- `plan/master-plan/10-master-backlog.md`
- `plan/master-plan/12-test-workstreams.md`

Current code paths relevant to this test plan:

- `app/services/vane.py`
- `app/services/orchestrator.py`
- `app/api/routes.py`
- `README.md`

## Current implementation assumptions to validate

Based on the current code, MP-04 validation should assume the following until proven otherwise:

- `POST /research` maps to backend execution mode `research` in `app/api/routes.py`
- `app/services/orchestrator.py` calls `self.vane.deep_search(...)` only for selected modes `deep` and `research`
- `app/services/vane.py` currently sends Vane a payload with:
  - `query`
  - `sources`
  - `optimizationMode`
  - `stream: false`
  - `chatModel.providerId`
  - `chatModel.key`
  - `embeddingModel.providerId`
  - `embeddingModel.key`
- `app/services/vane.py` currently parses only:
  - `body.message`
  - `body.sources[*].metadata.title`
  - `body.sources[*].metadata.url`
  - `body.sources[*].content`
- `app/services/orchestrator.py` currently stores the Vane result in `legacy.deep_synthesis` when `include_legacy=true`, but the main response payload is built from grounded evidence and may not visibly expose useful Vane output
- Vane failures currently append a warning and continue rather than aborting the whole request

These assumptions should be re-checked if implementation changes during MP-04.

## Acceptance targets

### Target 1 - Backend correctly calls Vane

For `POST /research` requests that should use Vane, the backend must issue a Vane request with the expected model/provider ids, optimization mode, and source mapping.

Pass indicators:

- backend logs or test doubles show exactly one Vane request per intended research execution path unless retries are explicitly added
- request payload fields match the expected Vane contract used by direct testing
- backend depth-to-Vane optimization mapping matches canonical plan guidance
- source-mode mapping is stable and intentional

Fail indicators:

- backend never calls Vane for a request that should attempt it
- backend calls Vane with the wrong provider ids or model keys
- backend sends the wrong optimization mode for the requested depth
- backend sends a malformed or incomplete payload versus the direct known-good baseline

### Target 2 - Backend correctly parses Vane responses

When Vane returns a successful payload, the backend must preserve the useful parts of that payload in a form that diagnostics or the response surface can prove it was received and understood.

Pass indicators:

- the returned Vane text payload is captured without being silently dropped
- parsed Vane sources preserve title and URL when present
- empty or partial source arrays do not crash the request
- response-shape variations are handled predictably or flagged clearly

Fail indicators:

- Vane responds successfully but backend diagnostics or payload show no meaningful sign of the result
- parsing errors collapse the whole request without a deliberate fallback path
- source metadata is lost even though Vane returned it
- backend treats a non-empty successful Vane payload as effectively empty

### Target 3 - Timeout and fallback behavior is safe

When Vane is too slow, unavailable, or returns an error, `/research` must still return a grounded response or explicit degraded behavior rather than hanging indefinitely or failing opaquely.

Pass indicators:

- Vane timeout is bounded by configured backend timeout behavior
- timeout produces a visible warning or diagnostic marker
- backend continues with grounded non-Vane synthesis or fallback search path as designed
- total request latency stays within an intentional degraded-mode budget

Fail indicators:

- request hangs beyond configured timeout expectations
- timeout causes an uncaught exception or blank response
- fallback silently removes useful evidence without any diagnostic trace
- fallback behavior differs unpredictably between similar failure cases

### Target 4 - Direct and backend Vane behavior are comparable

Using the same query and same Vane configuration, direct Vane and backend-driven Vane should not diverge so much that backend output looks like Vane was never called.

Pass indicators:

- backend request semantics are provably aligned with the direct request
- backend diagnostics or surfaced fields show that Vane returned substantive content when direct Vane did
- backend answer may be more grounded or filtered than direct Vane, but should still show recognizable Vane contribution when MP-04 intends it to be surfaced
- backend no longer returns only snippet-style output for cases where direct Vane produced strong long-form content and no fallback/error condition occurred

Fail indicators:

- direct Vane returns a strong result while backend shows no sign of a successful Vane branch
- backend behavior looks identical whether Vane succeeds, times out, or is disabled
- backend request semantics differ enough from the direct baseline that parity claims are not meaningful

### Target 5 - Vane is now surfaced correctly

MP-04 is complete only if successful Vane output is inspectable and not effectively invisible.

Pass indicators:

- at least one supported backend response surface or diagnostic path clearly shows the successful Vane result
- that surfaced output is attributable to the same request and not confused with grounded compiler findings
- operators can distinguish among Vane success, Vane error, and Vane timeout outcomes
- repo documentation and tests align on where Vane output is expected to appear

Fail indicators:

- successful Vane output is only inferable indirectly from logs with no response-side visibility
- a successful Vane call still yields an empty or meaningless surfaced Vane block
- there is no stable contract for how to inspect whether backend Vane succeeded

## Test method

Use a layered test approach:

1. code-path inspection to confirm intended control flow
2. focused unit or integration tests with mocked Vane responses
3. manual or scripted end-to-end parity checks against a real Vane instance using the known-good config
4. regression checks for timeout and fallback behavior

Prefer deterministic fixtures for parsing and fallback tests. Use live Vane calls only for parity and final acceptance checks because live latency and content will vary.

## Test data and environment

### Known-good direct baseline

Use the configuration recorded in `plan/master-plan/07-known-good-direct-vane-config.md`:

- chat provider id: `29a86a6a-721c-414f-bb0b-67a4f5a2d8fc`
- chat model key: `opencode-go/mimo-v2-omni`
- embedding provider id: `481e7ec6-873e-4e8d-ad58-e49b214d8729`
- embedding model key: `text-embedding-3-small`

Use this as the backend parity baseline before interpreting any mismatch as a Vane quality problem.

### Representative queries

Use at least these categories:

- research-heavy comparison query
- recommendation query with tradeoffs
- specific factual synthesis query
- one query already known to produce strong direct Vane output from prior notes

Suggested anchor query from existing notes:

- `What are the main causes of recent bee population decline, and which interventions have the strongest evidence of helping?`

### Required backend knobs

For acceptance runs, capture the effective values of:

- `VANE_ENABLED`
- `VANE_URL`
- `VANE_DEFAULT_MODE`
- Vane timeout setting from config/runtime
- Vane chat provider env id name and resolved value
- Vane embedding provider env id name and resolved value
- backend request depth (`quick`, `balanced`, `quality`)
- `include_legacy` and `include_debug` if used to inspect diagnostics

## Detailed scenarios

### Scenario 1 - Backend issues the expected Vane request

Purpose:

Prove that the backend request payload sent by `app/services/vane.py` matches the known-good direct semantics.

Setup:

- use a Vane test double or HTTP capture layer
- enable Vane in backend config
- send `POST /research` with `depth=balanced` and `source_mode=all`

Steps:

- submit a backend `/research` request with a representative research query
- capture the outbound request sent to `POST {VANE_URL}/api/search`
- record the JSON payload
- compare it against the expected direct payload shape

Validate:

- `query` matches exactly
- `sources` maps from backend `source_mode` correctly
- `optimizationMode` is correct for the requested depth
- `stream` is `false`
- `chatModel.providerId` and `chatModel.key` match configured values
- `embeddingModel.providerId` and `embeddingModel.key` match configured values

Failure examples:

- wrong provider id env resolution
- `balanced` unexpectedly mapped to an unintended mode
- source mapping differs from direct baseline
- request omits chat or embedding model blocks

### Scenario 2 - Depth-to-optimization mapping stays correct

Purpose:

Prove that backend depth selection produces the intended Vane optimization mode behavior.

Setup:

- use a Vane request capture test double
- run separate requests for `depth=quick`, `depth=balanced`, and `depth=quality`

Steps:

- issue the same query through `/research` for each supported depth
- capture the outbound Vane payload for each run

Validate:

- `quick -> speed`
- `quality -> quality`
- `balanced -> configured default if valid, else balanced`
- query-complexity escalation inside `_select_vane_depth()` is intentional and documented when it upgrades a balanced request to quality semantics

Failure examples:

- quick requests call Vane with `balanced`
- quality requests do not map to `quality`
- balanced requests change modes unpredictably across identical inputs

### Scenario 3 - Successful Vane response is parsed and surfaced

Purpose:

Prove that a successful Vane response is preserved in backend output rather than dropped.

Setup:

- use a mocked Vane response containing:
  - a non-empty `message`
  - at least two sources with `metadata.title`, `metadata.url`, and `content`
- call `/research` with `include_legacy=true`

Steps:

- return the mocked successful Vane payload from the Vane stub
- inspect the backend response payload and diagnostics

Validate:

- backend response completes successfully
- parsed Vane content appears in the expected surfaced location
- `legacy.deep_synthesis` or the designated replacement surface contains the Vane `message`
- source titles and URLs are preserved
- diagnostics make it possible to tell Vane succeeded

Failure examples:

- `message` missing despite successful mock response
- sources array always empty after parsing
- Vane success not visible anywhere in response-side inspection

### Scenario 4 - Partial Vane response does not break the backend

Purpose:

Prove that response parsing is resilient to incomplete but non-failing Vane payloads.

Setup:

- mock several Vane responses:
  - `message` present, no sources
  - sources present, missing metadata fields
  - empty `message`, non-empty sources
  - unknown extra fields

Steps:

- run one `/research` request per mock shape
- inspect payload, warnings, and status

Validate:

- backend returns a valid response each time
- missing metadata degrades gracefully to defaults where current code expects them
- unknown fields are ignored safely
- diagnostics make degraded parsing observable when appropriate

Failure examples:

- missing metadata crashes parsing
- partially valid Vane payload is treated as a fatal backend error
- successful but sparse Vane result becomes indistinguishable from no Vane attempt

### Scenario 5 - Vane timeout triggers clean fallback

Purpose:

Prove that slow Vane does not hang `/research` and that fallback behavior remains visible.

Setup:

- configure a Vane stub that exceeds backend timeout
- run `POST /research` with a query that would normally attempt Vane

Steps:

- submit the request
- measure total latency
- inspect warnings, diagnostics, and returned answer quality

Validate:

- request finishes without hanging indefinitely
- timeout is reflected as a warning, error marker, or equivalent diagnostic signal
- backend still returns a grounded research response or a defined degraded response
- response remains structurally valid

Failure examples:

- request blocks until client timeout instead of backend timeout
- timeout produces HTTP 500 without useful diagnostics
- backend returns an apparently normal result but hides that Vane timed out

### Scenario 6 - Vane HTTP error triggers clean fallback

Purpose:

Prove that HTTP-level Vane failures do not collapse `/research`.

Setup:

- mock Vane responses with `500`, `502`, and malformed JSON if practical

Steps:

- run `/research` against each failure mode
- inspect warnings and returned payload

Validate:

- backend returns a usable response when fallback is allowed
- warnings or diagnostics distinguish HTTP failure from timeout failure where possible
- no malformed Vane response poisons grounded citations already collected by the backend

Failure examples:

- backend crashes on malformed JSON from Vane
- provider trace or diagnostics lose the failure reason
- fallback path strips all useful answer content unnecessarily

### Scenario 7 - Direct Vane versus backend parity on the same query

Purpose:

Prove that backend Vane integration is no longer grossly mismatched with direct Vane.

Setup:

- use the known-good direct Vane config
- choose one query with historically strong direct Vane output
- use matching source selection and optimization semantics as closely as possible

Steps:

- run the query directly against Vane and save the request and response
- run the same query through backend `/research`
- capture backend diagnostics and surfaced Vane fields
- compare request semantics first, then compare response behavior

Validate:

- backend request semantics match direct request semantics closely enough for a fair comparison
- if direct Vane returns substantive long-form output, backend response visibly reflects successful Vane participation unless fallback or post-processing intentionally suppresses it with a documented reason
- backend may reframe or ground the answer differently, but must not look as though Vane never ran

Failure examples:

- direct Vane succeeds with rich output but backend surfaced Vane block is empty
- backend answer is purely snippet-style despite successful direct Vane and no indicated fallback
- backend request differs from direct request on provider/model/mode and makes comparison invalid

### Scenario 8 - Vane disabled path remains explicit and safe

Purpose:

Prove that disabling Vane does not break research while still making the disabled state clear.

Setup:

- set `VANE_ENABLED=false`
- run representative `/research` requests

Steps:

- submit at least one balanced and one quality-depth request
- inspect warnings, diagnostics, and payload shape

Validate:

- backend returns valid grounded research output without Vane
- diagnostics make it clear that Vane was not used by configuration
- response shape remains stable enough for clients

Failure examples:

- Vane-disabled requests fail unexpectedly
- response falsely suggests Vane succeeded
- disabling Vane changes unrelated response contracts

## Comparison rubric for direct versus backend behavior

When comparing direct and backend runs for the same query, score these dimensions:

- request parity: same query, same sources, same optimization mode, same provider/model ids
- response visibility: backend clearly exposes that Vane produced output
- message retention: core Vane message survives parsing and surfacing
- source retention: backend preserves a meaningful subset of Vane source metadata
- behavioral coherence: backend answer meaningfully reflects successful Vane participation instead of appearing identical to a no-Vane path
- fallback correctness: if backend diverges from direct because of timeout or validation fallback, that reason is inspectable

Do not require word-for-word equivalence. Backend is allowed to ground, trim, or combine Vane content with retrieved evidence. The key acceptance question is whether successful Vane output is still materially visible and correctly handled.

## Success criteria for "Vane is now surfaced correctly"

Declare MP-04 successful only if all of the following are true:

- at least one backend-supported inspection surface shows successful Vane content for a request where direct Vane also succeeds
- that surfaced content includes the substantive Vane text payload, not only a boolean success marker
- Vane source parsing preserves useful metadata for at least representative successful responses
- timeout and HTTP failure paths return valid backend responses with visible diagnostics or warnings
- direct and backend Vane runs using the same baseline config are no longer grossly mismatched in a way that suggests backend output was dropped
- tests or fixtures exist for both successful parsing and fallback/error behavior

Do not declare success if any of the following remain true:

- Vane success is visible only in server logs
- `legacy.deep_synthesis` or its replacement remains empty for successful Vane responses
- backend cannot distinguish timeout, disabled, and HTTP-error outcomes clearly enough to debug
- parity cannot be evaluated because backend request semantics still differ from the direct baseline

## Evidence to capture during MP-04 validation

For the final review packet, capture:

- one outbound backend-to-Vane request example for each supported depth mapping under test
- one successful mocked Vane parsing fixture and observed backend response
- one timeout or HTTP-error fallback example with observed diagnostics
- one direct-Vane versus backend side-by-side run using the same query and known-good config
- file references for any tests added or updated during MP-04

## Minimum recommended automated coverage

At minimum, add or update tests that cover:

- Vane request payload construction in `app/services/vane.py`
- Vane response parsing for success and partial-success shapes
- orchestrator behavior when Vane succeeds
- orchestrator behavior when Vane times out or returns an error
- response-side visibility of successful Vane output

## Exit decision

MP-04 should be marked complete when:

- request parity with the known-good direct baseline is demonstrated
- parsing coverage proves successful Vane payloads are not dropped
- timeout and fallback behavior are bounded and inspectable
- backend response or diagnostics now surface successful Vane output clearly enough for operators and clients to verify

If any of those remain unproven, keep MP-04 open even if direct Vane itself still works.

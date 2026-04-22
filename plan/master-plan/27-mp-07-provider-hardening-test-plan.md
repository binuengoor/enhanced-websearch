# MP-07 Provider Hardening Test Plan

This artifact defines how to validate MP-07 provider expansion and hardening without overstating completion before live resilience checks are finished.

It is intentionally test-focused.
It treats provider routing, cooldown policy, and mode-aware provider selection as the core acceptance surface for this milestone.

## Scope

This plan covers:

- mode-aware provider preference ordering in the router
- provider cooldown behavior by failure type
- config validation for provider preference names
- LiteLLM-backed provider onboarding changes that expand provider coverage without new Python adapters
- regression protection for provider trace and health reporting
- manual validation needed before MP-07 can move to done

This plan does not cover:

- broad answer-quality benchmarking owned by MP-08
- research synthesis correctness owned by MP-03 and MP-04
- Open WebUI wrapper behavior owned by MP-06
- long-term metrics dashboards or automated production alerting

## Baseline references

Use these repo artifacts as the source of truth while running this plan:

- `plan/master-plan/02-recommended-execution-order.md`
- `plan/master-plan/10-master-backlog.md`
- `plan/master-plan/11-dev-workstreams.md`
- `plan/master-plan/12-test-workstreams.md`
- `plan/master-plan/13-status-tracker.md`

Current code paths relevant to this test plan:

- `app/providers/router.py`
- `app/providers/base.py`
- `app/providers/litellm_search.py`
- `app/providers/searxng.py`
- `app/core/config.py`
- `config/config.yaml`
- `config/config.sample.yaml`
- `tests/test_provider_router.py`
- `tests/test_config_provider_preferences.py`

## MP-07 acceptance anchor

MP-07 is only complete when all of the following are true:

- provider ordering can be specialized by mode without breaking weighted rotation semantics inside each preference bucket
- cooldown behavior distinguishes rate limits, auth failures, and transient failures in a way that improves resilience
- config validation blocks impossible provider preference declarations before runtime
- provider additions or enablement changes can be expressed through config with minimal adapter churn when the provider already matches the LiteLLM search shape
- provider trace and health surfaces remain truthful and useful for operators
- live validation demonstrates reduced exhaustion pressure or better fallback behavior under realistic failures

## Current implementation observations to validate

These observations come from the current `mp-07-provider-hardening` branch state and should be re-checked during review:

- router ordering now accepts `provider_preferences` and groups providers into preferred, neutral, and avoided buckets by mode
- rotation is preserved within the preferred group rather than pinning the same provider first every time
- cooldown application now varies by provider failure type and may wait for the configured failure threshold before cooling down transient failures
- config loading now rejects `provider_preferences` entries that mention undeclared provider names
- LiteLLM-backed provider entries can now declare `litellm_provider` and rely on config load to derive the final `/search/<provider>` path
- branch tests cover router ordering, cooldown behavior, skip-in-cooldown behavior, and config validation, but live environment validation has not yet been completed here

## Proposed validation model

Use a layered test strategy:

1. config validation tests for known and unknown provider preference names
2. deterministic router unit tests for ordering, cooldown, and attempt accounting
3. static config review to confirm mode specialization matches intended provider roles
4. controlled integration checks with a local or staging backend using real provider credentials where available
5. manual resilience checks under forced provider failures and rate limits

Prefer deterministic automated coverage for routing policy correctness. Reserve live upstream calls for final acceptance because they depend on keys, quotas, and network conditions.

## Test matrix

Validate these scenarios at minimum:

- normal fast-mode routing with preferred providers available
- research-mode routing where preferred providers differ from fast mode
- deep-mode routing where one provider is explicitly avoided
- transient provider failure below threshold
- transient provider failure at threshold
- rate-limit failure with provider-specific retry interval
- auth failure with immediate longer cooldown
- provider already in cooldown while another provider remains healthy
- config file with valid provider preference names
- config file with invalid provider preference names
- LiteLLM-backed provider entry using `litellm_provider` without explicit `path`

For each path, compare:

- provider order chosen by the router
- attempts consumed versus skipped providers
- cooldown seconds applied
- provider trace status values
- provider health snapshot fields after the event
- config load result or validation error

## Router ordering validation

### Objective

Prove that provider specialization by mode works without destroying rotation fairness inside the preferred set.

### Method

Use `tests/test_provider_router.py` plus targeted manual inspection or small harness runs against `ProviderRouter._pick_order(...)`.

### Required checks

- preferred providers move ahead of neutral providers for the configured mode
- avoided providers move to the back for the configured mode
- providers not mentioned remain in the neutral group
- router cursor rotation still affects order inside the preferred group
- behavior without a mode still follows the base weighted rotation path

### Evidence to capture

- test output for ordering cases
- one concise table of expected order for `fast`, `research`, and `deep`
- note of any ties or weighting behavior that operators should understand

## Cooldown policy validation

### Objective

Prove that failure-type-aware cooldown handling improves resilience and preserves meaningful fallback behavior.

### Required cases

Run at least these cases:

- `RateLimitError` with `cooldown_seconds` override
- `AuthProviderError` with immediate cooldown
- `TransientProviderError` before threshold
- `TransientProviderError` at threshold
- success after previous failure to confirm state reset
- provider skipped because cooldown is still active

### Expected validation outcomes

- rate limits honor provider-specific retry intervals when supplied
- auth failures cool down immediately for longer than a standard transient failure
- transient failures do not immediately sideline a provider until the configured threshold is met
- success resets failure counts, cooldown state, and prior failure metadata
- skipped providers do not consume an attempt budget during routed search

### Suggested evidence

- test output for cooldown cases
- one recorded provider health snapshot per failure class
- one provider trace example showing `skipped_cooldown`

## Config validation and onboarding checks

### Objective

Prove that configuration remains safe as provider diversity increases.

### Required checks

- `load_config(...)` accepts preference names that map to declared providers
- `load_config(...)` rejects preference names that do not exist in the provider list
- `litellm-search` providers default `api_key_env` to `LITELLM_API_KEY` when unset
- `litellm_provider` auto-expands to the expected `/search/<provider>` path
- sample and live config stay aligned enough that onboarding guidance remains accurate

### Suggested evidence

- automated config validation results
- one effective-config example showing an auto-derived path
- short review note comparing `config/config.yaml` and `config/config.sample.yaml`

## Provider trace and health reporting validation

### Objective

Prove that operators can still understand what the router did after the hardening changes.

### Required checks

- routed search trace records `success`, `empty`, `transient`, and `skipped_cooldown` cases appropriately
- health snapshot fields capture failure type, cooldown duration, failure reason, and reset on success
- empty-result tracking remains distinguishable from hard failure tracking
- new routing behavior does not hide which provider actually served the response

### Suggested evidence

- captured trace examples from unit tests or a local harness
- one sample `/providers/health` response from a running environment if available

## Live resilience validation

### Objective

Gather the remaining evidence needed to decide whether MP-07 can move from in-progress to done.

### Preconditions

- environment has the required provider credentials and endpoints configured
- backend starts successfully with the MP-07 branch config
- a controlled way exists to trigger provider failure or temporary disablement

### Required checks

- run a small query set through `fast`, `research`, and `deep` paths and record the leading providers chosen
- force or simulate a rate limit on a preferred provider and verify fallback reaches the next suitable provider
- simulate an auth failure and verify cooldown plus fallback behavior
- observe whether preferred ordering improves source diversity for research/deep without obviously harming fast-mode latency
- confirm free-tier exhaustion pressure does not simply move to one new default provider

### Suggested evidence

- request logs with provider trace for each mode
- observed latency notes for each mode
- brief operator note on whether source diversity actually improved

## Manual acceptance runbook

Run this acceptance flow after automated checks pass:

1. start the backend with the MP-07 branch config
2. run config validation and router unit tests
3. issue at least one query per mode and capture provider traces
4. trigger a provider rate-limit or disablement scenario and observe fallback behavior
5. inspect `/providers/health` after failures and again after recovery
6. compare observed behavior to the configured `provider_preferences`

## Success criteria for "provider hardening works"

Decide that MP-07 passes only when all of the following are true:

- mode-aware provider ordering works as configured and remains rotation-friendly
- cooldown policy behaves differently by failure type in the intended ways
- invalid provider preference config fails fast during config load
- LiteLLM-backed provider onboarding remains mostly config-only when the normalized search shape already exists
- provider trace and health data remain operationally useful
- live validation shows resilience improvements under at least one realistic failure mode

## Exit artifacts

Captured in `28-mp-07-review-report.md`:
- automated test existence confirmed (router and config validation)
- live degraded-path fallback evidence for fast-mode (disabled preferred, transient failure threshold)
- research-mode degraded evidence (multiple research-cycle fallback with empty results)
- provider trace examples showing skip → fallback → success patterns
- remaining non-blocking follow-up items documented

## Live validation result: PASS

Completed 2026-04-22. See `28-mp-07-review-report.md` for full evidence table.

# MP-07 Provider Hardening Review Report

Status: PASS

Reviewed branch: `mp-07-provider-hardening`
Reviewed scope:
- `app/core/config.py`
- `app/providers/router.py`
- `app/providers/base.py`
- `app/providers/litellm_search.py`
- `app/providers/searxng.py`
- `config/config.yaml`
- `config/config.sample.yaml`
- `tests/test_provider_router.py`
- `tests/test_config_provider_preferences.py`
Validation date: 2026-04-22

## Findings

- PASS: Mode-aware provider preference ordering is implemented in `app/providers/router.py`. The router now groups providers into preferred, neutral, and avoided buckets for a selected mode while preserving cursor-based rotation inside the preferred bucket.
- PASS: Cooldown handling is hardened by failure class. The router now treats rate limits, auth failures, and transient provider failures differently instead of applying the same cooldown policy to every exception.
- PASS: Routed-search tests cover mixed traces, cooldown skips, failure-threshold behavior, success reset behavior, and preferred/avoided ordering in `tests/test_provider_router.py`.
- PASS: Config validation now rejects provider preference entries that reference undeclared provider names in `app/core/config.py`, with direct coverage in `tests/test_config_provider_preferences.py`.
- PASS: LiteLLM-backed provider onboarding is simpler. `litellm_provider` now auto-expands to `/search/<provider>` paths during config load, reducing config duplication and lowering the cost of enabling additional compatible providers.
- PASS: Live degraded-path fallback validated with two concrete cases.

## Acceptance evidence captured 2026-04-22

**Case 1 — Fast-mode disabled preferred provider fallback (ews-mp07-nosx, port 18092):**

- POST `/search` inside container with `searxng` disabled
- Live logs: `event=provider_skip ... provider=searxng status=cooldown cooldown_until=0.0`, then `event=provider_attempt ... provider=brave-search attempt=1`, then `event=provider_success`
- HTTP 200 with real results returned
- **Proves:** top fast-preferred provider is unavailable → fallback to next preferred provider → success

**Case 2 — Fast-mode transient failure threshold cooldown (isolated throwaway container, port 18094):**

- Container pointed at unreachable searxng URL (`http://10.255.255.1:9999`)
- Request 1: `searxng` times out (`error_type=ConnectTimeout`), fallback to `brave-search attempt=2`, success. Health after: `consecutive_failures=1`, `last_failure_type=transient`, `last_cooldown_seconds=0` (no cooldown yet)
- Request 2: `searxng` times out again, now `cooldown_seconds=90`, fallback to `brave-search attempt=2`, success. Health after: `consecutive_failures=2`, `cooldown_until=<future epoch>`, `last_cooldown_seconds=90`
- **Proves:** transient failures do not immediately cool down a provider; threshold (failure_threshold=2) triggers cooldown correctly; fallback still succeeds during cooldown window

**Research-mode degraded evidence (ews-mp07-no-searx-exa, port 18093):**

- POST `/research` with `searxng` and `exa` both disabled
- Research cycle 1: `brave-search` used (preferred research bucket also includes tavily/firecrawl/linkup but cursor/rotation decides ordering); returned `result_count=0`, router continued
- Research cycle 1 continued: `serper` used as attempt 2, `result_count=9`, success
- Research cycle 2: `brave-search` used again with 20 results, success
- **Proves:** research-mode fallback works when top research preferences are unavailable; empty-result does not block router from advancing to next provider

## Live validation performed by

Subagent `mp07-live-fallback` — spawned 2026-04-22, runtime 4m17s.
Used in-container `urllib.request` for live HTTP validation; host-to-container port access was unreliable from the shell environment.

## Remaining non-blocking follow-up

These items are documented but do not block merge:

1. **Missing regression test:** No automated coverage for `litellm_provider` auto-deriving `/search/<provider>` path and defaulting `api_key_env` to `LITELLM_API_KEY`. Suggested: add one focused test in `tests/test_config_provider_preferences.py`.
2. **Sample config under-represents operator surface:** `config/config.sample.yaml` only shows `research` preferences; live config has different policies for `fast`, `research`, and `deep`. Expand sample or mark it explicitly as minimal/example-only.
3. **Trace semantics note:** Disabled providers are logged as `status=cooldown cooldown_until=0.0` because `_is_ready()` treats `enabled=false` the same as not-ready. Operationally fallback works, but trace semantics blur "disabled" vs "cooling down". Low priority — worth noting for future trace cleanliness.
4. **Terminology cleanup deferred:** The repo is intentionally transitional; master-plan docs now define end state as `/research depth=balanced|quality`, but runtime still exposes `mode=deep|research` and `depth=quick|balanced|quality`. An initial compatibility inventory now exists, but broad rename/cleanup should still wait until MP-07 is merged.

## Conclusion

MP-07 implementation and live validation are complete. The milestone is merge-ready.
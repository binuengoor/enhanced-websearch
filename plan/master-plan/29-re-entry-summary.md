# Re-entry Summary

This note is the short continuity document for picking work back up after time away.
It is not the canonical detailed plan.
Use it as the quick orientation layer, then jump into the linked master-plan artifacts for specifics.

## What this app is

`enhanced-websearch` is the canonical backend service for search and research in this project.
It serves three client surfaces:

- direct HTTP API
- MCP tools mounted on the same app
- a thin Open WebUI wrapper

The backend owns the real work:

- query normalization and planning
- mode and routing decisions
- provider rotation, fallback, and cooldown policy
- fetch/extract and evidence gathering
- grounded synthesis for long-form research
- diagnostics, traces, and cache reporting

For the product definition and architecture stance, start with:

- `plan/master-plan/01-master-architecture.md`
- `plan/master-plan/03-decision-summary.md`
- `README.md`

## What we are building toward

The target is a local-first, agent-friendly Perplexity-style research backend where clients stay thin and the backend owns retrieval plus synthesis.

Practical shape:

- `/search` is the fast, predictable, mostly retrieval-first path
- `/research` is the bounded long-form path with grounded synthesis and citations
- the Open WebUI wrapper and MCP layer mirror backend semantics instead of inventing their own behavior

The intended delivery order and rationale are already documented in:

- `plan/master-plan/02-recommended-execution-order.md`
- `plan/master-plan/10-master-backlog.md`

## What is completed so far

As of the current branch state, these milestones are effectively complete and already documented elsewhere:

- MP-00: contract and decision freeze
- MP-01: quick search hardening
- MP-02: planning and routing foundation
- MP-03: research synthesis refactor
- MP-04: Vane integration repair
- MP-05: progress streaming
- MP-06: Open WebUI wrapper repair

The current status board is the authoritative snapshot:

- `plan/master-plan/13-status-tracker.md`

Detailed milestone-level validation and review artifacts already exist for MP-01 through MP-06 in:

- `plan/master-plan/15-mp-01-quick-search-hardening-test-plan.md`
- `plan/master-plan/16-mp-01-review-report.md`
- `plan/master-plan/17-mp-02-planning-routing-foundation-test-plan.md`
- `plan/master-plan/18-mp-02-review-report.md`
- `plan/master-plan/19-mp-03-research-synthesis-refactor-test-plan.md`
- `plan/master-plan/20-mp-03-review-report.md`
- `plan/master-plan/21-mp-04-vane-integration-test-plan.md`
- `plan/master-plan/22-mp-04-review-report.md`
- `plan/master-plan/23-mp-05-progress-streaming-test-plan.md`
- `plan/master-plan/24-mp-05-review-report.md`
- `plan/master-plan/25-mp-06-wrapper-repair-test-plan.md`
- `plan/master-plan/26-mp-06-review-report.md`

In plain terms, the project has already moved from a rough search wrapper toward a more coherent backend with:

- stable quick-search behavior
- bounded planning artifacts and routing diagnostics
- evidence-first research synthesis instead of stitched excerpts
- repaired Vane integration paths
- progress streaming for long-running work
- a thinner Open WebUI wrapper aligned with backend contracts

## What is still in progress or not done

### MP-07 is the active milestone

Current work is provider expansion and hardening on branch `mp-07-provider-hardening`.

What appears to be done already:

- mode-aware provider preference ordering
- cooldown behavior by failure type
- config validation for provider preference names
- simpler LiteLLM-backed provider onboarding via `litellm_provider`
- targeted router/config test coverage
- initial terminology inventory created so cleanup can proceed safely after MP-07 without changing current compatibility behavior

What is still missing before MP-07 should be treated as complete:

- captured live degraded-path fallback proof under realistic provider failure conditions
- final review-ready evidence that the new ordering and cooldown policy improve resilience in practice

Use these as the active MP-07 references:

- `plan/master-plan/27-mp-07-provider-hardening-test-plan.md`
- `plan/master-plan/28-mp-07-review-report.md`
- `plan/master-plan/13-status-tracker.md`
- `plan/master-plan/10-master-backlog.md`

### Later milestones are still open

Not started yet in the master plan:

- MP-08: quality gates and evaluation suite
- MP-09: optional product enhancements

Those are intentionally later-phase tasks. The current plan is to finish provider hardening and then add evaluation/quality controls before polishing optional product features.

MP-08 now has an initial planning artifact in:

- `plan/master-plan/30-mp-08-quality-gates-test-plan.md`

That artifact is intentionally lightweight. It defines the first benchmark buckets, regression-fixture strategy, gate categories, negative-fixture requirements, and baseline-comparison expectations needed to start implementation without overscoping the eval work.

## What the intended end state should look like

When the master plan is finished, this repo should look and behave like:

- one canonical backend for search and research behavior
- thin clients across HTTP, MCP, and Open WebUI
- fast `/search` behavior that is cheap, stable, and boring
- grounded `/research` behavior that returns synthesized answers with citations
- provider routing that is mode-aware, observable, and resilient under failures
- optional Vane usage only where it is validated and beneficial
- progress visibility for long-running research without a premature heavy job system
- explicit quality gates and regression coverage so answer quality does not silently drift

For the architectural target, use:

- `plan/master-plan/01-master-architecture.md`
- `plan/master-plan/02-recommended-execution-order.md`
- `plan/master-plan/04-implementation-guardrails.md`

## Best re-entry path

If someone is resuming work later, the shortest useful path is:

1. read `plan/master-plan/13-status-tracker.md`
2. read `plan/master-plan/29-re-entry-summary.md`
3. review MP-07-specific artifacts in `plan/master-plan/27-mp-07-provider-hardening-test-plan.md` and `plan/master-plan/28-mp-07-review-report.md`
4. inspect current branch/code changes for the remaining degraded-path validation work
5. use `plan/master-plan/30-mp-08-quality-gates-test-plan.md` to scope the first small benchmark/fixture implementation
6. only after that, move to MP-09 only if MP-08 validation is genuinely useful

## Scope note

This document intentionally avoids repeating detailed milestone breakdowns that already exist in the master-plan set.
Those source docs remain the canonical detailed planning and validation record.

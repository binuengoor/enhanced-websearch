# Status Tracker

Use this file to track live implementation progress.

Rule:

A milestone should only move to `done` after:

- implementation work is complete
- validation/testing is complete
- acceptance criteria pass
- review signs off

## Status board

| Milestone | Status | Dev | Test | Notes |
|---|---|---|---|---|
| MP-00 Contract and decision freeze | done | complete | pass | canonical docs added: 05/06/07 plus wrapper diagnosis artifact; public contract clarified as `/search` fast and `/research` research, with intended end-state `/research depth=balanced|quality`; compatibility caveat retained where implementation still references older terms |
| MP-01 Quick search hardening | done | complete | pass | merged to main; provider fallback/cooldown hardened, result budgeting added, empty-result cooldown regression fixed |
| MP-02 Planning and routing foundation | done | complete | pass | merged to main; structured RoutingDecision and ResearchPlan schemas, planner hooks, diagnostics wiring, schema-level bounds enforced |
| MP-03 Research synthesis refactor | done | complete | pass | merged to main; evidence/synthesis separation, clustered citation findings, mode-differentiated summary/direct_answer, corroboration fix, deep mode distinct behavior |
| MP-04 Vane integration repair | done | complete | pass | merged to main; multi-path answer/summary/content extraction, Vane synthesis promotion, mode-based timeouts, content-path fix for all lookup paths |
| MP-05 Progress streaming | done | complete | pass | merged to main; SSE streaming, ProgressEvent schema, stage transitions, duplicate-start fix, request_id in error events |
| MP-06 Open WebUI wrapper repair | done | complete | pass | merged to main; recency multi-unit fix, dict returns, SSE progress mapping, thin-wrapper preserved |
| MP-07 Provider expansion and hardening | in_progress | partial | partial | branch `mp-07-provider-hardening` adds mode-aware provider preferences, failure-type cooldown policy, LiteLLM provider onboarding cleanup, and config validation; targeted router/config tests passed in Docker/provisioned environments, and live smoke validation passed for the new ordering path, but degraded-path live fallback proof is still missing so the milestone is not review-ready yet |
| MP-08 Quality gates and evaluation suite | todo | not started | not started | |
| MP-09 Optional product enhancements | todo | not started | not started | |

## Suggested use with subagents

### Dev agent pattern

For a selected milestone:

- assign the dev workstream to a coding/dev subagent
- require it to report:
  - files changed
  - implementation summary
  - open risks
  - self-reported completion status

### Test agent pattern

After dev work completes:

- assign the matching test workstream to a separate testing/review subagent
- require it to report:
  - what was tested
  - observed results
  - pass/fail by acceptance criteria
  - regressions or risks

### Orchestrator rule

The orchestrator should only mark a milestone `done` if:

- dev agent says complete
- test agent says pass
- review does not find a blocking issue

## Notes

This file is intentionally lightweight. It should remain readable and manually maintainable.

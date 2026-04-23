# Master Plan

Merged planning set combining the strongest parts of:

- `plan/luna-plan`
- `plan/hermes-plan`

Purpose:

- establish one recommended direction
- preserve the high-level architecture clarity from Hermes
- preserve the implementation realism and Vane findings from Luna
- define the recommended execution order

## Files

- `01-master-architecture.md` - merged architecture and product definition
- `02-recommended-execution-order.md` - final phased order with rationale
- `03-decision-summary.md` - short top-level decisions and non-decisions
- `04-implementation-guardrails.md` - acceptance thresholds, mandatory pre-work, tool selection guidance, and frozen non-goals
- `05-mode-mapping.md` - canonical public/internal/Vane mode mapping for MP-00
- `06-search-non-goals.md` - canonical `/search` non-goals for MP-00
- `07-known-good-direct-vane-config.md` - canonical current direct Vane baseline for MP-00
- `05-open-webui-wrapper-diagnosis.md` - mandatory MP-00 diagnosis of why the wrapper is weaker than MCP
- `10-master-backlog.md` - milestone backlog with dependencies and done criteria
- `11-dev-workstreams.md` - development-focused work packages for delegation
- `12-test-workstreams.md` - independent testing tracks and validation scenarios
- `13-status-tracker.md` - lightweight live status board for orchestration and completion tracking
- `14-git-workflow.md` - local branch/commit workflow for safe parallel subagent execution
- `29-re-entry-summary.md` - concise continuity/background note for resuming work later
- `30-mp-08-quality-gates-test-plan.md` - initial MP-08 benchmark, fixture, and quality-gate plan
- `36-research-output-quality-plan.md` - audit of current `/research` output degradation and corrective direction
- `37-mp-10-research-output-preservation-implementation-plan.md` - executable backlog and milestone plan for preserving substantive Vane longform output
- `38-searxng-compat-endpoint-plan.md` - implementation plan for a compatibility-only `/compat/searxng` adapter backed by the existing provider router

## Core position

Keep `enhanced-websearch` as the canonical backend.

Do not replace it with the external repos.
Use external repos as reference material only.

## Key reality check

Direct Vane can work with the right model setup, but the current backend integration still does not surface Vane output correctly. That means architecture should assume:

- Vane is optional until validated
- direct provider retrieval remains the grounding backbone
- backend Vane integration needs repair before Vane is treated as core

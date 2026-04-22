# MP-08 Quality Gates and Evaluation Suite Test Plan

This artifact defines how to validate MP-08 without pretending this repo needs a giant eval platform.

It is intentionally test-focused.
It treats benchmark coverage, regression fixtures, and explicit quality-gate failures as the core acceptance surface for this milestone.

## Scope

This plan covers:

- a small benchmark query set that exercises the real `/search` and `/research` behavior this repo ships today
- regression fixtures that capture representative good and bad outputs for stable review
- quality-gate criteria for weak, generic, thin, and weakly grounded answers
- practical checks for citation coverage, contradiction handling, and answer specificity
- baseline-versus-candidate comparison for milestone acceptance
- lightweight execution patterns that can live in repo tests and docs without requiring hosted evaluation infrastructure

This plan does not cover:

- a production analytics platform
- LLM-as-judge fantasies with opaque scores as the only gate
- broad UI evaluation for Open WebUI
- provider-routing correctness already covered by MP-07
- research synthesis refactors already owned by MP-03 and MP-04

## Baseline references

Use these repo artifacts as the source of truth while running this plan:

- `README.md`
- `plan/master-plan/02-recommended-execution-order.md`
- `plan/master-plan/10-master-backlog.md`
- `plan/master-plan/11-dev-workstreams.md`
- `plan/master-plan/12-test-workstreams.md`
- `plan/master-plan/13-status-tracker.md`
- `plan/master-plan/29-re-entry-summary.md`

Current code paths likely touched by eventual MP-08 implementation:

- `app/api/routes.py`
- `app/services/orchestrator.py`
- `app/services/compiler.py`
- `app/models/contracts.py`
- `tests/`

## MP-08 acceptance anchor

MP-08 is only complete when all of the following are true:

- the repo has a named benchmark set small enough to run repeatedly but broad enough to catch obvious quality drift
- regression fixtures include both expected-good and intentionally weak/bad examples
- quality gates can fail answers for concrete reasons rather than vague "felt weak" judgments
- weak or generic answers are detectable for both quick `/search` and long-form `/research` paths
- groundedness checks consider the transitional contract reality: public `/research depth=balanced|quality`, compatibility acceptance of `depth=quick`, and internal orchestration still using `fast|research|deep`
- milestone acceptance compares candidate behavior against a recorded baseline instead of claiming improvement by impression only

## Transitional terminology guardrail

MP-08 docs and tests should use public endpoint vocabulary first:

- `/search` for concise fast behavior
- `/research` for long-form behavior
- `depth=balanced|quality` as the intended public research contract

Compatibility notes should remain explicit where needed:

- `depth=quick` is still accepted today for transitional clients and may appear in compatibility fixtures
- internal diagnostics and implementation may still reference `fast|research|deep`
- quality-gate artifacts should not force a premature repo-wide rename before the implementation is ready

## Proposed evaluation model

Use a layered model rather than one monolithic score:

1. benchmark query inventory grouped by answer type
2. stored regression fixtures for representative good, bad, and edge-case outputs
3. deterministic heuristic checks for obvious failure modes
4. bounded reviewer rubric for cases heuristics cannot judge alone
5. baseline-versus-candidate comparison recorded in one lightweight results table

Heuristics should catch the cheap failures first. Human review should only be needed for the narrower set of ambiguous answers.

## Benchmark buckets

Create a benchmark set with enough spread to expose common failure patterns.

Minimum buckets:

- factual lookup
- focused comparison
- recent or recency-sensitive topic
- technical how-to
- broad explainer or research synthesis
- contradiction-heavy topic
- sparse-evidence or uncertain topic

Suggested target size for first pass:

- 12 to 18 total benchmark queries
- at least 2 queries per major bucket
- at least 4 queries run through `/search`
- at least 8 queries run through `/research`

That is large enough to catch regressions and small enough to run during milestone work.

## Benchmark query design rules

Each benchmark query should include a compact metadata record with:

- stable query text
- endpoint under test: `/search` or `/research`
- public request knobs used, especially `depth`, `source_mode`, and recency filters where relevant
- why this query exists
- expected failure modes
- what "good enough" looks like

Prefer queries that are:

- realistic for actual users of this backend
- stable enough to re-run without daily churn unless they intentionally test recency
- capable of exposing generic-answer failure modes
- varied enough that one provider or one synthesis style cannot game the whole set

Avoid benchmark queries that are:

- so open-ended that every answer is unjudgeable
- dependent on hidden domain expertise no reviewer can apply consistently
- so volatile that the baseline expires every day

## Suggested initial benchmark set shape

The exact wording can be tuned during implementation, but the first MP-08 set should look roughly like this:

- factual `/search`: specific entity/date/value lookup where a short direct answer should be possible
- factual `/search`: constrained lookup with domain or recency filter
- comparison `/research`: compare two tools, vendors, or technical options with tradeoffs
- comparison `/research`: "A vs B for X" where weak answers collapse into generic pros/cons
- recent `/search`: topic where stale snippets are a risk
- recent `/research`: recent event or release requiring explicit caveats about freshness
- technical how-to `/research`: multi-step configuration or debugging question where actionable specificity matters
- technical how-to `/research`: error-remediation query where shallow answers become generic boilerplate
- broad explainer `/research`: concept explanation that still needs grounded synthesis rather than stitched snippets
- contradiction-heavy `/research`: topic with conflicting claims across sources
- sparse-evidence `/research`: niche question where the right behavior is cautious uncertainty, not invented confidence
- validation-control fixture: intentionally bad or thin answer for a real benchmark query to prove the gates fire

## Regression fixture strategy

Store fixtures in a form that stays easy to review in git.

Recommended fixture classes:

- request fixtures: the exact request payloads used for benchmark runs
- baseline response fixtures: one accepted reference response per benchmark case where stability is reasonable
- negative fixtures: intentionally weak or generic answers crafted from prior failures or manually reduced examples
- review notes: a compact statement of why a fixture is pass, borderline, or fail

Keep fixtures lightweight:

- prefer JSON or Markdown that can be diffed plainly
- avoid capturing every diagnostic field if they are noisy and not part of the quality contract
- preserve enough citations, findings, and summary text to judge groundedness and specificity

## Quality-gate categories

MP-08 should define gates by failure class, not one magic score.

Minimum gate categories:

- generic-answer gate
- thin-answer gate
- grounding/citation gate
- contradiction-handling gate
- unsupported-certainty gate
- regression gate against accepted baseline behavior

Each gate should be independently explainable in test output.

## Generic-answer gate

Objective:
Fail answers that read like boilerplate and could have been written without retrieval.

Common fail signals:

- answer mostly restates the question
- vague advice with no concrete entities, steps, dates, versions, or comparisons when the query requires them
- repetitive filler such as "it depends" without narrowing factors
- comparison answer gives symmetric generic pros/cons without citing meaningful differences
- research answer contains polished prose but few query-specific details

Suggested checks:

- low overlap between answer claims and cited source-specific nouns, dates, versions, or figures
- absence of concrete differentiators for comparison/how-to queries
- repeated generic phrases seen in known weak fixtures
- reviewer rubric asking whether the same answer could fit many unrelated queries with minor edits

## Thin-answer gate

Objective:
Fail answers that are too shallow for the endpoint and query class.

Common fail signals:

- `/research` response is barely longer or richer than a quick lookup
- findings are missing or trivially short for a broad query
- summary/direct answer omits the main tradeoff, caveat, or decision point the query asks for
- response stops after one narrow fact when the prompt clearly asks for synthesis

Suggested checks:

- minimum structural expectations by endpoint and bucket
- minimum count of meaningful findings or evidence-backed claims for research cases
- reviewer rubric asking whether the answer addresses the whole question rather than one fragment

## Grounding and citation gate

Objective:
Fail answers that are insufficiently supported or whose citations do not back the visible claims.

Common fail signals:

- long-form answer makes multiple substantive claims with little or no citation support
- citations exist but are weakly connected to the text they supposedly support
- sources list is present but claims are generic summaries not traceable to evidence
- answer sounds precise while evidence is sparse or low quality

Suggested checks:

- require non-trivial citation presence for `/research` benchmark cases unless the query is explicitly sparse-evidence
- require citations or source references for claims involving dates, numbers, comparisons, and recent developments
- verify a sampled set of visible claims against cited snippets or source metadata during review
- treat explicit uncertainty plus limited evidence as better than confident unsupported synthesis

## Contradiction-handling gate

Objective:
Fail answers that flatten disagreement into false certainty when sources conflict.

Common fail signals:

- contradiction-heavy query produces one-sided certainty with no caveat
- answer merges incompatible claims without acknowledging differences in source timing or scope
- response cherry-picks one source and ignores obvious disagreement surfaced elsewhere in the result set

Suggested checks:

- benchmark bucket specifically designed to surface conflicting evidence
- require answer to acknowledge disagreement, scope differences, or uncertainty where appropriate
- review whether the final synthesis reflects conflict rather than masking it

## Unsupported-certainty gate

Objective:
Fail answers that sound more confident than the evidence warrants.

Common fail signals:

- niche or sparse-evidence query answered with definitive wording and no caveat
- recent topic answered as settled despite stale or limited sourcing
- summary removes uncertainty that appears in the underlying evidence

Suggested checks:

- compare confidence language against evidence richness
- require caveats when source count is low, evidence is stale, or claims conflict
- include at least one sparse-evidence benchmark where the correct behavior is cautious limitation

## Baseline comparison gate

Objective:
Prevent silent drift by comparing candidate runs against an accepted baseline.

The first baseline can be modest.
It only needs to be honest and replayable.

Required comparison fields per benchmark case:

- pass or fail by gate category
- brief note on answer specificity
- brief note on citation sufficiency
- major regression yes or no
- overall pass, borderline, or fail

Candidate acceptance for the milestone should require:

- no new severe failures on existing pass cases
- at least one measurable improvement over the initial baseline on known weak cases
- no increase in generic-answer failures for the core `/research` set

## Negative-fixture validation

MP-08 should explicitly prove that the suite catches bad answers.

At minimum, include negative fixtures for:

- a generic comparison answer with no concrete differences
- a broad research answer with minimal citations or weak grounding
- a sparse-evidence answer that states a definitive conclusion without caveat
- a contradiction-heavy answer that ignores source disagreement

The suite should fail these fixtures for explicit reasons.
If a negative fixture passes, the gate is not strong enough yet.

## Review rubric for ambiguous cases

Some failures are not safely judgeable with heuristics alone.
Use a short reviewer rubric with yes or no prompts:

- does the answer directly address the full user question
- does it include concrete, query-specific details
- are the main claims grounded in visible citations or source-backed findings
- does it represent uncertainty and disagreement honestly
- would a reasonable user consider this materially better than a generic model-only answer

If two or more answers are ambiguous, prefer conservative "borderline" over forced "pass."

## Practical execution plan

Start small and keep it runnable by one engineer.

Phase 1:

- define benchmark inventory in repo
- define fixture format
- add a small runner or documented manual harness
- capture baseline outputs for the initial query set

Phase 2:

- add deterministic heuristic checks for generic/thin/grounding failures
- add negative fixtures to prove gates trigger
- record first baseline comparison table

Phase 3:

- tighten thresholds only where false positives are manageable
- add one or two benchmark cases if major blind spots remain
- avoid expanding scope until the first suite is actually useful

## Suggested artifact layout

One realistic starting layout would be:

- `plan/master-plan/30-mp-08-quality-gates-test-plan.md`
- `tests/fixtures/evals/benchmarks/*`
- `tests/fixtures/evals/baselines/*`
- `tests/fixtures/evals/negative/*`
- `tests/` runner or validation module for heuristic gates

The exact paths can change during implementation, but the suite should live with the repo and be git-reviewable.

## Manual acceptance runbook

Run this acceptance flow once the first MP-08 implementation exists:

1. execute the initial benchmark set against the current baseline branch or tagged baseline outputs
2. execute the same set against the candidate implementation
3. run heuristic gates against accepted-good and negative fixtures
4. review any borderline or contradictory results with the short rubric
5. record per-case pass, fail, or borderline plus major regression notes
6. only mark MP-08 done if known weak/generic cases are detected and candidate results are not worse than baseline on core scenarios

## Success criteria for "quality gates work"

Decide that MP-08 passes only when all of the following are true:

- benchmark cases exist for the major query buckets this backend actually serves
- fixtures are easy to review and rerun
- negative fixtures prove the gates catch generic, thin, weakly grounded, and overconfident answers
- baseline comparison is recorded in a lightweight repeatable form
- at least one known weak-answer pattern is measurably improved or reliably blocked
- the suite is small enough to keep using during future milestones

## Exit artifacts

Capture these artifacts before marking MP-08 complete:

- benchmark inventory with endpoint and purpose metadata
- first baseline results table
- negative fixtures with explicit expected failure reasons
- heuristic gate definitions and observed pass/fail behavior
- one follow-up note describing remaining blind spots or false-positive risks

## Open questions to resolve during implementation

- should `/search` quality checks focus mainly on result usefulness and specificity rather than prose quality
- how much citation enforcement is appropriate for `/search` responses that are intentionally concise
- which benchmark cases are stable enough to store as fixed baselines versus review-only dynamic cases
- whether the compiler should own part of the gate logic or whether test-only validation should remain the first step

## Notes

This plan is deliberately modest.
If MP-08 produces a trustworthy small suite that catches obvious quality drift, it succeeds.
If it turns into a sprawling eval framework before it proves value, it has gone off track.

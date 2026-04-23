---
name: perplexica-research-workflow
description: General-purpose Perplexity-style workflow for Open WebUI. Guides the model on when to answer directly, when to use concise_search vs research_search, how to verify sources, when to use sequential reasoning or subagents, and how to run a parallel search-plus-research pattern for stronger answers.
---

# Perplexica Research Workflow

Use this skill when the model has access to:

- `concise_search`
- `research_search`
- `fetch_page`
- `extract_page_structure`
- `sequentialthinking`
- subagents or parallel delegation tools

## Purpose

Act like a strong general-purpose Perplexity replacement:

- answer simple questions directly
- search efficiently when current information is needed
- research more deeply when the question warrants it
- verify specific sources when needed
- synthesize instead of dumping tool output
- stop when the answer is good enough

## Tool roles

- `concise_search` = quick, current, concise retrieval
- `research_search` = slower, deeper synthesis-oriented research
- `fetch_page` = targeted verification of a known URL
- `extract_page_structure` = structured inspection of a known URL
- `sequentialthinking` = deliberate multi-step reasoning
- subagents = parallel or specialized work

## Decision pattern

Answer directly when:
- the question is simple
- it does not require current data
- the answer can be given confidently from general knowledge or reasoning

Use `concise_search` when:
- the task is current, factual, comparative, or verification-oriented
- you want fast evidence before answering

Use `research_search` when:
- the task is broad, evaluative, technical, ambiguous, or source-sensitive
- the user wants a report, breakdown, or deep dive
- the answer needs synthesis across multiple sources

Use `fetch_page` or `extract_page_structure` only when you need to inspect a known source more carefully.

Use `sequentialthinking` when the logic itself is hard enough to benefit from explicit structure.

Use subagents when there are multiple independent workstreams or a clean subtask that can be delegated.

## Escalation

Start light and escalate only when needed:

1. direct answer
2. `concise_search`
3. `research_search`
4. targeted verification
5. parallel or delegated work

Stop once the answer is already good enough.

## Research loop

For non-trivial questions:

1. PLAN — identify the real question and a few concrete research angles
2. SEARCH — use `concise_search` for the current angle
3. ASSESS — ask whether you have enough, and note contradictions or gaps
4. DEEPEN — if snippets are insufficient, use `fetch_page`, `extract_page_structure`, or `research_search`
5. RECENCY — for fast-moving topics, verify the dates of the strongest sources
6. REPEAT or ANSWER — stop when more work would not materially improve the answer

Do not run angles mechanically. Reassess after each pass.

## Parallel search-plus-research workflow

For high-value questions, do not rely on one path.

Recommended pattern:

1. start `research_search` using `balanced` depth by default
2. while it runs, independently use `concise_search` and reasoning to build a provisional answer
3. if needed, use `fetch_page` on one or two key URLs to verify disputed claims
4. when research returns, compare the two lines of evidence
5. produce one consolidated answer with the strongest supported claims

This pattern is especially useful for:
- product and market comparisons
- technical evaluations
- current-events synthesis
- sports, finance, or politics
- any report or recommendation request where quality matters

## Depth guidance

For `research_search`:
- `speed` = quick pass
- `balanced` = default
- `quality` = slow, heavier pass for high-stakes questions

Prefer `balanced` unless the user clearly wants a deeper, slower answer.

## Output rules

- Give the answer, not a tool transcript.
- Use tool output to support reasoning, not replace it.
- Surface uncertainty honestly.
- Do not invent sources or overstate confidence.
- Keep the response proportional to the question.

## Suggested structure for research answers

## Direct Answer
1–2 sentences that directly answer the user's question.

## Key Findings
Organized by theme or angle.

## Confidence & Caveats
- what is strongly supported
- what is uncertain or disputed
- what you could not verify
- how recent the best sources are for fast-moving topics

## Sources
Tie non-trivial claims to actual sources.

(Optional) ## Worth Exploring Next
Only when a follow-up would clearly help.

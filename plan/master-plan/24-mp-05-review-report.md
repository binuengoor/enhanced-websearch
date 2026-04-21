# MP-05 Review Report

Status: FAIL

## Scope reviewed

- test plan: `plan/master-plan/23-mp-05-progress-streaming-test-plan.md`
- diff: `main..HEAD` for `app/api/routes.py`, `app/services/orchestrator.py`, `app/models/contracts.py`
- validation command: `python3 -m compileall app`

## Result

MP-05 is close, but it does not fully pass the quick review gate yet.

## Findings

1. Stage transitions are not fully meaningful or cleanly ordered.
   - `app/services/orchestrator.py` emits `state="search_started"` once before the loop and then again for every cycle.
   - This means clients see repeated `search_started` events instead of a clearer progression such as initial start followed by per-cycle progress and then downstream stages.
   - The later transitions to `evidence_gathering`, `synthesizing`, and `complete` are sensible, but the repeated start state weakens the event contract.

2. Streamed error events lose request identity.
   - `app/api/routes.py` catches exceptions in the SSE worker and emits a `ProgressEvent` with `request_id="unknown"`.
   - That makes error correlation weaker than the normal progress path, where a real orchestrator request id is generated.
   - Error handling exists, but the emitted error envelope is less useful than it should be.

## Checks

- ProgressEvent schema well-defined: PASS
  - `app/models/contracts.py` defines a compact schema with constrained `type` and `state` literals plus optional cycle, timing, and error metadata.

- Stage transitions meaningful and in order: FAIL
  - Overall flow trends in the right direction, but repeated `search_started` events make the sequence less meaningful.

- Streaming defaults to off / non-streaming still works: PASS
  - `app/api/routes.py` enables streaming only when `stream=true`; otherwise `/research` returns the normal JSON response path.

- SSE event format clean (`event:`, `data:`): PASS
  - `_sse_event()` emits standard SSE framing with `event:` and `data:` lines separated by a blank line.

- Error handling present: PASS with caveat
  - The SSE path catches exceptions and emits an `error` event, but request correlation is degraded because the fallback event uses `request_id="unknown"`.

## Command result

- `python3 -m compileall app`: PASS

## Recommendation

Do not mark MP-05 review as passed until the stage progression contract is cleaned up and streamed errors preserve a real request identifier.

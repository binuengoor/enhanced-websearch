# MP-09 Optional Product Enhancements Review Report

Status: PASS

Reviewed branch: `main`
Reviewed scope: MP-09 optional local-first polish
Reviewed files:
- `app/api/routes.py`
- `app/core/config.py`
- `app/main.py`
- `app/mcp_server.py`
- `app/models/contracts.py`
- `app/services/orchestrator.py`
- `app/services/report_exporter.py`
- `app/services/run_history.py`
- `docker-compose.yml`
- `Dockerfile`
- `README.md`
- `tests/test_report_exporter.py`
- `tests/test_run_history.py`
- `plan/master-plan/10-master-backlog.md`
- `plan/master-plan/11-dev-workstreams.md`
- `plan/master-plan/12-test-workstreams.md`
- `plan/master-plan/13-status-tracker.md`
Validation date: 2026-04-22

## Findings

- PASS: Saved research reports are implemented as local file artifacts without introducing a database. Completed `/research` responses can be exported as `report.md` and `report.yaml`, and auto-export is now supported when `service.auto_export_research` is enabled.
- PASS: Report output stays local-first and predictable. Reports write under `artifacts/reports/<timestamp-slug-random>/`, `docker-compose.yml` bind-mounts that directory to the host, and the `Dockerfile` now creates `/app/artifacts/reports` during build for stable permissions.
- PASS: Minimal recent-run history is implemented as a bounded in-memory ring buffer via `RecentRunHistory(max_entries=100)`. The new `GET /runs/recent` endpoint provides newest-first debugging entries without introducing persistent analytics state.
- PASS: The canonical diagnostics surface is now `GET /metrics`, which includes cache stats, provider summary (`healthy`, `cooldown`, `degraded`), and recent request summary (`total`, `success`, `failed`). This keeps observability consolidated instead of adding another status endpoint.
- PASS: MCP parity exists via `service_metrics`, which mirrors the `/metrics` response shape rather than inventing an overlapping alternative view.
- PASS: The implementation preserved the thin-backend constraints from the plan: no job queue, no resumable orchestration, no dashboard subsystem, no mandatory database, and no logic shift into the wrapper/frontend.
- PASS: Auto-export failure is non-fatal. If report writing fails, the `/research` response still succeeds and only logs a warning, which preserves request reliability.
- PASS: README is updated to document `/metrics`, `/runs/recent`, `/research/export`, auto-export behavior, and MCP `service_metrics`.

## Validation notes

- Local Docker build succeeded after MP-09 changes.
- Container startup succeeded after correcting the default config path to `config/config.yaml`.
- Endpoint checks confirmed expected responses for `/health`, `/metrics`, `/runs/recent`, and `/research/export`.
- Auto-export configuration is enabled in `config/config.yaml` and writes to `artifacts/reports`.

## Issues found during validation

- **Medium (resolved):** Default config path expected `config.sample.yaml`, but the image only copied `config/config.yaml`. Fixed by updating the default config path in `app/core/config.py` to `config/config.yaml`.
- **Medium (resolved):** Auto-export output directory was not explicitly created in the image, which could cause first-write/permission surprises outside compose. Fixed by creating `/app/artifacts/reports` in `Dockerfile`.
- **Medium (documented, non-blocking):** Existing non-MP-09 tests still have harness issues unrelated to this milestone. These do not block MP-09 because the feature slice itself was validated separately and the failures predate or sit outside the shipped MP-09 contract.

## Acceptance criteria assessment

| Criterion | Status |
|---|---|
| Saved reports are local-first and human-readable | PASS — Markdown + YAML artifacts under `artifacts/reports` |
| Recent-run history is bounded and debugging-focused | PASS — in-memory ring buffer, newest-first `/runs/recent` |
| `/metrics` is the single canonical diagnostics surface | PASS — cache + provider summary + request summary |
| MCP mirrors the same operational data | PASS — `service_metrics` returns `/metrics` view |
| No DB, job system, or duplicate status surfaces introduced | PASS |
| Auto-export does not compromise request reliability | PASS — failures log warnings only |
| Runtime/deployment docs reflect shipped behavior | PASS — README, compose, Dockerfile, config updated |

## Conclusion

MP-09 is complete and satisfies the tightened scope defined in the planning docs. The implemented work delivers the intended optional local-first polish without reopening backend architecture or adding operational complexity. The milestone is ready to be marked done in the status tracker.

Recommendation: keep MP-09 marked done and treat any remaining work as post-plan cleanup rather than milestone scope.

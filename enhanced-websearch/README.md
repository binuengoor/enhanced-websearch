# Enhanced Websearch Open WebUI Wrapper

This directory contains the thin Open WebUI client tool.

- enhanced_websearch.py: single-file wrapper that calls the standalone backend service over HTTP

All heavy research behavior moved to the standalone backend at repo root.

## Wrapper behavior

The wrapper exposes three Open WebUI entrypoints:

- elevated_search
- fetch_page
- extract_page_structure

Each method proxies to service endpoints:

- POST /internal/search
- POST /fetch
- POST /extract

The wrapper is intentionally small and uses stdlib HTTP so it remains robust in constrained Open WebUI runtime environments.

## Config

Admin valves:

- SERVICE_BASE_URL
- REQUEST_TIMEOUT

Minimal wrapper setup (recommended):

- set SERVICE_BASE_URL only
- keep REQUEST_TIMEOUT default unless your network is slow
- configure search providers, Vane, routing, cache, and mode budgets at service level (.env + config/config.yaml)

User valves:

- mode
- include_citations
- show_status_updates
- max_iterations

Environment defaults:

- EWS_SERVICE_BASE_URL (default: http://enhanced-websearch:8091)
- EWS_BEARER_TOKEN (optional)
- EWS_REQUEST_TIMEOUT (default: 25)

## Deployment relationship

1. Deploy the backend service from repo root.
2. Verify backend health at GET /health.
3. Import enhanced_websearch.py into Open WebUI workspace tools.
4. Set SERVICE_BASE_URL to the backend URL.
5. Optionally tune per-user valves (mode, citations, status updates, max_iterations).

The wrapper returns backend JSON output directly, so the backend response contract is the canonical contract.

The public POST /search endpoint is now reserved for Perplexity-compatible callers; the wrapper uses POST /internal/search.

If `EWS_BEARER_TOKEN` is set, the wrapper forwards `Authorization: Bearer <token>` to the backend.

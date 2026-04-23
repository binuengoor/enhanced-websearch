# Enhanced Websearch Service

Standalone search, fetch, and Vane-proxy compatibility backend for Open WebUI Perplexity-style tooling.

## What this is

This service is the local search/fetch compatibility backend. It owns:

- deterministic `/search` behavior and query normalization
- mode semantics (auto, fast, deep, research)
- provider routing with cooldowns, fallback, and budgets
- search result normalization and fusion
- page fetch/extraction and optional PDF extraction
- compatibility surfaces such as `/compat/searxng`
- diagnostics, provider traces, cache reporting, recent-run history, and MCP tools mounted on the same ASGI app at `/mcp`

Refactor note:

- `/search` stays local and deterministic.
- `/research` is being simplified toward a transparent Vane-backed flow.
- older local planner/compiler/orchestrator research machinery still exists during the transition, but it should be treated as transitional rather than the target architecture.

The Open WebUI workspace tool becomes a thin HTTP wrapper.

## Project structure

- app/main.py: FastAPI app + dependency wiring
- app/api/routes.py: HTTP endpoints
- app/core/config.py: YAML + env config loading
- app/providers/: provider implementations + router
- app/services/: fetch/extract, ranking, Vane integration, and transitional planner/orchestrator code still being simplified
- app/cache/memory_cache.py: in-memory TTL cache
- config/config.yaml: final service configuration used by compose
- config/config.sample.yaml: template you can copy from
- docker-compose.yml: single publishable service + optional dependencies

## Adding LiteLLM-backed providers

If LiteLLM already exposes a search backend behind the same normalized `/search/<provider>` contract, you can add a new provider without changing Python code.

Add a provider entry like this to `config/config.yaml`:

```yaml
- name: jina-search
  kind: litellm-search
  enabled: true
  weight: 1
  timeout_s: 12
  base_url: ${LITELLM_SEARCH_BASE_URL}
  litellm_provider: jina-search
```

Notes:
- `litellm_provider` auto-expands to `path: /search/<litellm_provider>` during config load.
- `api_key_env` defaults to `LITELLM_API_KEY` for `litellm-search` providers unless explicitly overridden.
- You can still set `path` manually if a provider needs a nonstandard LiteLLM route.
- If a provider is not exposed through the existing LiteLLM search shape, it still needs a new adapter in `app/providers/`.

## API

### POST /search

Perplexity Search API-compatible endpoint for concise, low-latency results.

Request body supports at minimum:

{
  "query": "string or string[]",
  "max_results": 10
}

It returns a JSON object with `id`, `results`, and optional `server_time`.
Each result contains `title`, `url`, and `snippet`.

Optional Perplexity-style extensions are also accepted, including:

- display_server_time
- country
- max_tokens
- max_tokens_per_page
- search_language_filter
- search_domain_filter
- search_recency_filter
- search_after_date_filter
- search_before_date_filter
- last_updated_after_filter
- last_updated_before_filter
- search_mode
- mode (deprecated; ignored for behavior selection)

Behavior notes:

- `/search` always executes in a fast profile with lightweight heuristic planning.
- `search_mode: "auto"` is accepted and behaves the same as omitting `search_mode` entirely.
- Use `/research` for long-form output.

The endpoint also enforces:

- domain filters
- language filters (best-effort by URL/language metadata)
- recency/date filters when date metadata is available
- per-page and total token limits for snippets

Unknown fields are ignored.

### POST /research

Transparent Vane research proxy.

Behavior:

- validates the local `ResearchRequest` contract
- translates the request into Vane `POST /api/search`
- always sends `stream: true` upstream
- proxies upstream SSE output, status code, and selected headers as-is
- does not run local planner/compiler/orchestrator synthesis

Request body:

{
  "query": "string",
  "source_mode": "web|academia|social|all",
  "depth": "quick|balanced|quality",
  "max_iterations": 4,
  "include_debug": false,
  "include_legacy": false,
  "strict_runtime": false,
  "user_context": {}
}

Vane mapping:

- `query` -> `query`
- `source_mode` -> `sources` (`web`, `academic`, `discussions`)
- `depth` -> `optimizationMode` (`quick -> speed`, `balanced -> balanced`, `quality -> quality`)
- provider ids and model keys come from Vane config

Response:

- `text/event-stream`
- upstream Vane body is passed through without local normalization
- HTTP 504 is returned for upstream timeouts
- upstream non-2xx responses are surfaced with the upstream status code and a cleaned error detail

### POST /internal/search

Deprecated internal endpoint.

- no real caller is documented in this repo
- retained temporarily as a compatibility shim for local concise search only
- returns a deprecation warning in the response body


Request body:

{
  "query": "string",
  "mode": "auto|fast|deep|research",
  "source_mode": "web|academia|social|all",
  "depth": "quick|balanced|quality",
  "max_iterations": 4,
  "include_citations": true,
  "include_debug": false,
  "include_legacy": false,
  "strict_runtime": false,
  "user_context": {}
}

Response shape is stable and includes:

- query, mode, direct_answer, summary
- findings, citations, sources, follow_up_queries
- diagnostics: runtime, routing_decision, research_plan, query_plan, provider_trace, cache, errors, warnings
- timings.total_ms
- confidence

Optional legacy output is opt-in with include_legacy.

### GET /health

Returns service liveness.

### GET /providers/health

Returns provider-level state:

- enabled
- cooldown_until
- consecutive_failures
- last_success_at
- last_failure_at
- last_failure_reason

### POST /fetch

Fetches and extracts a single page.

### POST /extract

Returns structured metadata for a single page.

### GET /config/effective

Returns effective non-secret config for debugging.

### GET /metrics

Returns the canonical lightweight observability snapshot for the service, including:

- search cache stats
- page cache stats
- provider summary (`healthy`, `cooldown`, `degraded`)
- recent request summary (`total`, `success`, `failed`)

### GET /runs/recent

Returns a bounded newest-first recent-run history for debugging.
Each entry includes endpoint, query, mode, success/failure, citation/source counts, confidence, and capped warnings/errors.

### GET /compat/searxng

Compatibility-only SearxNG-style endpoint for clients that expect `GET /search?format=json` semantics.

Accepted query params include:

- `q`
- `format` (`json` only)
- `categories`
- `engines`
- `language`
- `pageno`
- `time_range`

Behavior notes:

- General/web requests use the normal provider-rotating search path and return a SearxNG-like envelope.
- Image/video requests are detected from `categories` and `engines` tokens such as `images`, `videos`, `youtube`, and `google images`.
- Media requests currently pass through to the configured upstream SearxNG provider so media-specific fields like `img_src`, `thumbnail`, and `iframe_src` keep the expected shape.
- Backend/provider failures degrade to HTTP 200 with an empty SearxNG-like payload.
- This adapter is separate from the canonical `POST /search` and `POST /research` contracts.

### POST /research/export

Exports a completed `/research` response as local artifacts without changing the normal response contract.
Artifacts are written as:

- `report.md`
- `report.yaml`

under `artifacts/reports/<timestamp-slug-random>/`.

If `service.auto_export_research: true` is enabled, completed `/research` requests are exported automatically after successful completion.

### MCP tools at /mcp

The same FastAPI app also mounts a FastMCP server at `/mcp`.

Available tools:

- search
- research
- fetch_page
- extract_page_structure
- health_check
- providers_health
- service_metrics

Tool guidance:

- `search` is the concise search path with only the few useful knobs kept (`max_results`, `display_server_time`, `search_mode`, `search_recency_filter`, `search_recency_amount`, `country`). `search_mode` accepts `auto`, `web`, `academic`, or `sec`; `auto` is normalized to the default behavior and sent to the backend the same as omitting the field; `search_recency_filter` accepts `none`, `hour`, `day`, `week`, `month`, or `year`; `search_recency_amount` (default `1`) lets you request multi-unit windows such as `3` + `month`.
- `research` proxies the backend `/research` route, which in turn proxies Vane streaming research output. `source_mode` accepts `web`, `academia`, `social`, or `all`; `depth` accepts `quick`, `balanced`, or `quality`, with `quick` treated as compatibility-only.
- `fetch_page` and `extract_page_structure` are for page-level inspection and debugging.
- `health_check`, `providers_health`, and `service_metrics` are for operational checks. Prefer `service_metrics` for the single aggregated view.

Optional bearer token:

- set `EWS_BEARER_TOKEN` to require `Authorization: Bearer <token>` on the HTTP surfaces, including `/mcp`
- leave it blank for local/trusted setups

MCP host-header behavior:

- FastMCP matches the full `Host` header, and the service now allows both bare hosts and wildcard-port entries.
- To allow local/LAN MCP clients, set `EWS_MCP_ALLOWED_HOSTS` with either bare hosts or wildcard-port entries (for example `localhost`, `localhost:*`, `127.0.0.1`, `127.0.0.1:*`, `10.1.1.150`, `10.1.1.150:*`).
- Plain host values are normalized to both bare and wildcard-port form by the service.

## Planning foundation

`/internal/search` and `/research` currently expose two thin structured planning artifacts in diagnostics:

- `routing_decision`: requested mode, selected mode, source of the decision, heuristic reason, and detected query profile
- `research_plan`: bounded step list with the initial query-expansion plan and max iteration budget

Current behavior remains intentionally conservative:

- mode selection is still heuristic-first
- `/search` remains on the concise fast path
- long-form execution is in transition and should not be treated as a stable local orchestration contract
- the new schema is there to keep endpoint contracts stable while the implementation is simplified

## Provider routing behavior

Router strategy:

- weighted rotating provider order
- checks provider cooldown state
- retries up to mode-specific budget
- marks provider cooldown after rate-limit or repeated failures
- falls back to next eligible provider
- records provider trace in diagnostics

Mode defaults (configurable):

- fast: low attempts, low page count, one pass
- deep: broader retrieval, optional Vane
- research: iterative cycles with bounded follow-up queries
- auto: heuristic selection based on query profile

## Caching

In-memory cache for v1:

- search cache keyed by normalized query/mode/options
- page fetch cache keyed by URL
- separate TTL for recency-sensitive queries
- hit/miss and cache stats exposed in diagnostics

## Configuration

1. Copy .env.example to .env
2. Edit config/config.yaml and env values
3. Keep secrets in env vars only

LiteLLM gateway setup defaults:

- use one shared key: LITELLM_API_KEY
- provider enablement is controlled by per-provider flags (applies to all providers)
  - `EWS_PROVIDER_SEARXNG_ENABLED=true|false`
  - `EWS_PROVIDER_BRAVE_SEARCH_ENABLED=true|false`
  - `EWS_PROVIDER_SERPER_ENABLED=true|false`
  - `EWS_PROVIDER_EXA_ENABLED=true|false`
  - `EWS_PROVIDER_TAVILY_ENABLED=true|false`
  - `EWS_PROVIDER_FIRECRAWL_ENABLED=true|false`
  - `EWS_PROVIDER_LINKUP_ENABLED=true|false`
- when a flag is unset, YAML `providers[].enabled` is used

Transitional LLM compiler settings (still read by the current code, but headed toward removal as `/search` stays deterministic and `/research` moves to Vane proxying):

- set `EWS_COMPILER_ENABLED=true` to enable
- set `EWS_COMPILER_MODEL_ID` to the LiteLLM chat model id to use
- set `EWS_COMPILER_BASE_URL` to your LiteLLM base (`.../v1` recommended)
- set `EWS_COMPILER_API_KEY` for a compiler-specific auth key
- if `EWS_COMPILER_API_KEY` is unset, compiler falls back to `LITELLM_API_KEY`
- the same compiler is also used as a final research quality gate; if a long-form `research` response looks thin or generic, the service can fall back to a quick grounded search path before returning
- `/research` requires at least one configured LLM path: either Vane (`VANE_ENABLED=true` plus `VANE_URL`) or the compiler (`EWS_COMPILER_ENABLED=true` plus `EWS_COMPILER_BASE_URL` and `EWS_COMPILER_MODEL_ID`)

Transitional LLM planner fallback (`/search` profile selection):

- set `EWS_PLANNER_LLM_FALLBACK_ENABLED=true` to allow LLM-assisted selection of `depth` and `max_iterations`
- default is disabled and remains heuristic-only
- if LLM planner selection fails for any reason, `/search` automatically falls back to the heuristic profile
- treat this as compatibility wiring during the simplification work, not as the preferred long-term `/search` design

When compiler output is accepted, each result may also include optional grounding metadata:

- `citation_ids`: candidate ids used to ground the item
- `evidence_spans`: short grounded excerpts
- `confidence`: normalized 0..1 confidence from compiler
- `grounding_notes`: optional short rationale

Vane defaults:

- `VANE_ENABLED` controls whether research flows can call Vane
- during the transition, `/research` can still run when the compiler is configured even if Vane is disabled, because the old local path has not been fully removed yet
- `VANE_DEFAULT_MODE` defaults to balanced and can be set to speed, balanced, or quality
- expect Vane to become the primary `/research` backend as the simplification lands

Startup logs include:

- active and disabled providers
- routing policy and cooldown settings
- whether Vane is enabled, its URL, and its default optimization mode
- cache settings

YAML sections:

- service
- routing
- provider_preferences
- modes
- providers
- cache
- scraping
- vane
- compiler (transitional)
- planner (transitional)
- logging

Provider preferences let you bias routing per mode without changing provider weights:

```yaml
provider_preferences:
  research:
    prefer: [exa]
    avoid: [searxng]
```

Notes:
- `prefer` providers are tried before neutral providers for that mode.
- `avoid` providers are still eligible, but moved to the back of the mode-specific order.
- Preferences preserve the router's normal weighted rotation within each group.
- Config load now fails fast if a preferred or avoided provider name does not match a configured provider.

## Run

Local:

- pip install -r requirements.txt
- uvicorn app.main:app --host 0.0.0.0 --port 8091

Docker compose:

- cp .env.example .env
- docker compose up -d --build

## Open WebUI wrapper guidance

Use a single-file Open WebUI tool that:

- accepts tool arguments
- calls POST /internal/search on this service
- returns the service JSON unchanged
- optionally proxies /fetch and /extract

Keep wrapper logic minimal and stateless.

The thin wrapper now emits periodic Open WebUI status updates while waiting for the backend, but it still performs a blocking HTTP request under the hood. Default backend request timeout is `EWS_REQUEST_TIMEOUT=60`; raise it further only if your backend is legitimately slow.

## Integration Migration Notes

Use this mapping after the `/search` + `/research` split:

- Perplexity-compatible clients: call `POST /search`.
- Long-form structured research clients: call `POST /research`.
- Advanced internal callers that need explicit mode control (`auto|fast|deep|research`): use `POST /internal/search`.

MCP guidance:

- `perplexity_search` should target `POST /search` and only send deprecated `mode` when explicitly requested.
- `research_search` should target `POST /research` for explicit long-form behavior.
- `search` can remain as a back-compat alias for rich payload paths.

OpenWebUI thin-client guidance:

- Add explicit methods for concise `POST /search` and long-form `POST /research`.
- Keep any existing rich/internal method as back-compat where needed.

## Open WebUI System Prompt (Token-Efficient)

```markdown
You are **Perplexica**, a research assistant in Open WebUI.

Use tools only when they improve answer quality.

Available tools:
- `concise_search` (primary concise web search via `/search`)
- `research_search` (primary long-form research via `/research`)
- `fetch_page` (targeted source verification)
- `extract_page_structure` (targeted structure/metadata extraction)

Behavior:
- Answer directly for simple, stable questions.
- Use `concise_search` for quick factual lookups and lightweight comparisons.
- Use `research_search` for broad, technical, evaluative, or source-sensitive questions.
- Treat `balanced` as the normal public research depth; reserve `quality` for deliberate higher-latency work.
- Use `fetch_page` / `extract_page_structure` only for targeted verification.
- Stop when answer quality is sufficient.

Escalation:
- Start with the lightest useful path.
- Escalate only when needed: `concise_search` -> `research_search`.
- In `research_search`, escalate depth only as needed. Prefer `balanced` first; use `quick` only when maintaining compatibility with older clients/prompts; escalate to `quality` for clearly harder requests.

`concise_search` knobs:
- `search_mode`: `auto|web|academic|sec` (`auto` = default behavior, equivalent to omitting it)
- `search_recency_filter`: `none|hour|day|week|month|year`
- `search_recency_amount`: integer (for example `3` + `month`)
- `country`, `max_results`

`research_search` knobs:
- `source_mode`: `web|academia|social|all`
- `depth`: `quick|balanced|quality`
- `max_iterations`

Output handling:
- Synthesize results; do not dump raw JSON.
- Prefer evidence-backed claims.
- If evidence is weak, conflicting, or stale, say so clearly.

Style:
- Clear, direct, and proportionate to question complexity.
- For simple questions: brief direct answer.
- For complex/research questions: concise synthesis with caveats and sources.

Rules:
- Never invent citations, URLs, or claims.
- Never present uncertain findings as certain.
- Ask at most one clarifying question only when needed.
- If tools fail, report failure and continue with best-effort reasoning.
```

## Optional bearer token

If you want to protect the HTTP service and MCP server, set `EWS_BEARER_TOKEN` in `.env`.
The Open WebUI wrapper will forward the same token automatically when it is present.

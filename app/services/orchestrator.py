from __future__ import annotations

import hashlib
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

from app.cache.memory_cache import InMemoryCache
from app.core.config import AppConfig
from app.models.contracts import PerplexitySearchRequest, PerplexitySearchResponse, PerplexitySearchResult
from app.models.contracts import SearchDiagnostics, SearchRequest, SearchResponse
from app.providers.router import ProviderRouter
from app.services.fetcher import PageFetcher
from app.services.planner import QueryPlanner
from app.services.ranking import Ranker
from app.services.vane import VaneClient


logger = logging.getLogger(__name__)


class ResearchOrchestrator:
    def __init__(
        self,
        config: AppConfig,
        router: ProviderRouter,
        search_cache: InMemoryCache,
        page_cache: InMemoryCache,
        fetcher: PageFetcher,
        planner: QueryPlanner,
        ranker: Ranker,
        vane: VaneClient,
    ):
        self.config = config
        self.router = router
        self.search_cache = search_cache
        self.page_cache = page_cache
        self.fetcher = fetcher
        self.planner = planner
        self.ranker = ranker
        self.vane = vane

    async def execute_search(self, req: SearchRequest) -> SearchResponse:
        request_id = uuid.uuid4().hex[:8]
        started = time.perf_counter()
        selected_mode = self.planner.choose_mode(req.mode, req.query)
        mode_budget = self.config.modes[selected_mode]

        logger.info(
            "event=search_start request_id=%s mode=%s query=%r source_mode=%s depth=%s max_iterations=%s include_citations=%s include_legacy=%s",
            request_id,
            selected_mode,
            req.query,
            req.source_mode,
            req.depth,
            req.max_iterations,
            req.include_citations,
            req.include_legacy,
        )

        plan = self.planner.initial_plan(req.query, selected_mode)
        all_result_sets: List[List[Dict[str, Any]]] = []
        provider_trace: List[Dict[str, Any]] = []
        warnings: List[str] = []
        errors: List[str] = []
        followups: List[str] = []
        search_cache_state = {"hits": 0, "misses": 0}

        iterations = 1
        if selected_mode == "research":
            iterations = min(req.max_iterations, mode_budget.max_queries)

        seen_titles: List[str] = []
        for cycle in range(iterations):
            query_text = plan[min(cycle, len(plan) - 1)]["text"] if cycle < len(plan) else req.query
            if cycle > 0 and selected_mode == "research":
                query_text = self.planner.followup_query(req.query, seen_titles)
                plan.append({"text": query_text, "purpose": "followup"})
                followups.append(query_text)

            logger.info(
                "event=search_cycle request_id=%s cycle=%s/%s mode=%s query=%r",
                request_id,
                cycle + 1,
                iterations,
                selected_mode,
                query_text,
            )

            rows, trace, cache_meta = await self._search_once(
                query=query_text,
                mode=selected_mode,
                source_mode=req.source_mode,
                depth=req.depth,
                max_attempts=mode_budget.max_provider_attempts,
                request_id=request_id,
            )
            provider_trace.extend(trace)
            search_cache_state["hits"] += cache_meta["hits"]
            search_cache_state["misses"] += cache_meta["misses"]

            if rows:
                all_result_sets.append(rows)
                seen_titles.extend([r.get("title", "") for r in rows])
            else:
                errors.append(f"No provider returned results for cycle {cycle + 1}")

            if selected_mode != "research":
                break

        fused = self.ranker.fuse(all_result_sets)
        diverse = self.ranker.diversity_filter(fused, mode_budget.max_pages_to_fetch)

        pages = await self._fetch_pages(req.query, diverse)
        citations = self._build_citations(req.query, pages)
        findings = self._build_findings(citations)
        sources = self._build_sources(citations)
        confidence = self._confidence(pages, errors)

        deep_synthesis = None
        if selected_mode in {"deep", "research"}:
            vane_depth = self._select_vane_depth(req.query, req.depth, selected_mode)
            logger.info(
                "event=vane_selected request_id=%s mode=%s query=%r depth=%s selected_vane_depth=%s",
                request_id,
                selected_mode,
                req.query,
                req.depth,
                vane_depth,
            )
            deep_synthesis = await self.vane.deep_search(req.query, req.source_mode, vane_depth)
            if deep_synthesis.get("error"):
                warnings.append(f"Vane unavailable: {deep_synthesis['error']}")

        direct_answer = findings[0]["claim"] if findings else ""
        summary = f"Collected {len(citations)} citations across {len(sources)} sources using mode={selected_mode}."

        runtime = {
            "strict_runtime": req.strict_runtime,
            "provider_count": len(self.router.health_snapshot()),
            "vane_enabled": bool(self.config.vane.enabled),
        }

        diagnostics = SearchDiagnostics(
            warnings=warnings,
            errors=errors,
            runtime=runtime,
            query_plan=plan,
            iterations=iterations,
            coverage_notes=[
                f"fused_results={len(fused)}",
                f"fetched_pages={len(pages)}",
            ],
            search_count=len(plan),
            fetched_count=len(pages),
            ranked_passage_count=len(citations),
            provider_trace=provider_trace,
            cache={
                "search": search_cache_state,
                "page": self.page_cache.stats(),
            },
        )

        payload: Dict[str, Any] = {
            "query": req.query,
            "mode": selected_mode,
            "direct_answer": direct_answer,
            "summary": summary,
            "findings": findings,
            "citations": citations if req.include_citations else [],
            "sources": sources,
            "follow_up_queries": followups,
            "diagnostics": diagnostics.model_dump(),
            "timings": {"total_ms": int((time.perf_counter() - started) * 1000)},
            "confidence": confidence,
        }

        if req.include_legacy:
            payload["legacy"] = {
                "results_ranked": fused,
                "results_scraped": pages,
                "deep_synthesis": deep_synthesis,
            }
            logger.info("event=legacy_block_included request_id=%s legacy_keys=%s", request_id, list(payload["legacy"].keys()))

        logger.info(
            "event=search_complete request_id=%s mode=%s query=%r citations=%s sources=%s confidence=%s total_ms=%s errors=%s warnings=%s",
            request_id,
            selected_mode,
            req.query,
            len(citations),
            len(sources),
            confidence,
            payload["timings"]["total_ms"],
            len(errors),
            len(warnings),
        )

        return SearchResponse.model_validate(payload)

    async def execute_perplexity_search(self, req: PerplexitySearchRequest) -> PerplexitySearchResponse:
        request_id = req.trace_id or uuid.uuid4().hex[:8]
        queries = self._normalize_queries(req.query)
        mode = req.mode or self._infer_compat_mode(req)
        source_mode = self._map_search_mode(req.search_mode)
        results: List[PerplexitySearchResult] = []
        seen_urls: set[str] = set()

        logger.info(
            "event=perplexity_search_start request_id=%s query_count=%s max_results=%s mode=%s search_mode=%s",
            request_id,
            len(queries),
            req.max_results,
            mode,
            req.search_mode or "none",
        )

        for query in queries:
            internal = SearchRequest(
                query=query,
                mode=mode,
                source_mode=source_mode,
                depth=self._select_depth(req),
                max_iterations=self._select_iterations(req),
                include_citations=True,
                include_debug=False,
                include_legacy=False,
                strict_runtime=False,
                user_context={
                    "client": req.client or "open-webui",
                    "trace_id": request_id,
                    "country": req.country,
                    "max_tokens": req.max_tokens,
                    "max_tokens_per_page": req.max_tokens_per_page,
                    "search_language_filter": req.search_language_filter or [],
                    "search_domain_filter": req.search_domain_filter or [],
                    "search_recency_filter": req.search_recency_filter,
                    "search_after_date_filter": req.search_after_date_filter,
                    "search_before_date_filter": req.search_before_date_filter,
                    "last_updated_after_filter": req.last_updated_after_filter,
                    "last_updated_before_filter": req.last_updated_before_filter,
                },
            )
            response = await self.execute_search(internal)
            items = self._perplexity_results_from_response(response)
            items = self._filter_perplexity_results(items, req.search_domain_filter or [])
            for item in items:
                if item.url in seen_urls:
                    continue
                seen_urls.add(item.url)
                results.append(item)
                if len(results) >= req.max_results:
                    break
            if len(results) >= req.max_results:
                break

        server_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z") if req.display_server_time else None
        return PerplexitySearchResponse(id=f"search_{request_id}", results=results[: req.max_results], server_time=server_time)

    async def fetch(self, url: str) -> Dict[str, Any]:
        cached = self.page_cache.get(f"fetch:{url}")
        if cached:
            logger.info("event=fetch_cache_hit url=%s", url)
            return cached

        logger.info("event=fetch_start url=%s", url)
        page = await self.fetcher.fetch(url)
        self.page_cache.set(f"fetch:{url}", page, self.config.cache.page_cache_ttl_s)
        logger.info(
            "event=fetch_complete url=%s title=%r source=%s error=%s",
            url,
            page.get("title"),
            page.get("source"),
            page.get("error"),
        )
        return page

    async def extract(self, url: str) -> Dict[str, Any]:
        logger.info("event=extract_start url=%s", url)
        result = await self.fetcher.extract(url)
        logger.info(
            "event=extract_complete url=%s title=%r headings=%s links=%s error=%s",
            url,
            result.get("title"),
            len(result.get("headings", [])),
            len(result.get("links", [])),
            result.get("error"),
        )
        return result

    def metrics(self) -> Dict[str, Any]:
        return {
            "cache_search": self.search_cache.stats(),
            "cache_page": self.page_cache.stats(),
            "providers": len(self.router.health_snapshot()),
        }

    async def _search_once(
        self,
        query: str,
        mode: str,
        source_mode: str,
        depth: str,
        max_attempts: int,
        request_id: str,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, int]]:
        options = {
            "limit": self.config.modes[mode].max_pages_to_fetch,
            "source_mode": source_mode,
            "depth": depth,
            "request_id": request_id,
        }
        key = self._cache_key(query, mode, options)
        cached = self.search_cache.get(key)
        if cached:
            logger.info("event=search_cache_hit request_id=%s mode=%s query=%r", request_id, mode, query)
            return cached, [{"provider": "cache", "status": "hit"}], {"hits": 1, "misses": 0}

        logger.info("event=search_cache_miss request_id=%s mode=%s query=%r", request_id, mode, query)
        rows, trace = await self.router.routed_search(query, options, max_attempts=max_attempts)
        ttl = self._ttl_for_query(query)
        if rows:
            self.search_cache.set(key, rows, ttl)
            logger.info(
                "event=search_cache_store request_id=%s mode=%s query=%r ttl=%s result_count=%s",
                request_id,
                mode,
                query,
                ttl,
                len(rows),
            )
        return rows, trace, {"hits": 0, "misses": 1}

    async def _fetch_pages(self, query: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        pages: List[Dict[str, Any]] = []
        for row in rows:
            url = row.get("url", "")
            if not url:
                continue
            page = await self.fetch(url)
            content = page.get("content", "")
            page["quality_score"] = self.ranker.quality_score(query, row, content)
            page["snippet"] = row.get("snippet", "")
            page["provider"] = row.get("provider", "")
            pages.append(page)
        pages.sort(key=lambda x: x.get("quality_score", 0.0), reverse=True)
        return pages

    def _normalize_queries(self, query: Any) -> List[str]:
        if isinstance(query, list):
            return [item.strip() for item in query if isinstance(item, str) and item.strip()]
        if isinstance(query, str) and query.strip():
            return [query.strip()]
        return []

    def _infer_compat_mode(self, req: PerplexitySearchRequest) -> str:
        if len(self._normalize_queries(req.query)) > 1:
            return "research"
        if req.search_recency_filter or (req.max_tokens and req.max_tokens >= 50000):
            return "research"
        if req.max_tokens_per_page and req.max_tokens_per_page >= 4096:
            return "deep"
        if req.search_domain_filter or req.search_language_filter or req.country or req.search_mode in {"academic", "sec"}:
            return "deep"
        if req.max_results <= 3:
            return "fast"
        return "auto"

    def _map_search_mode(self, search_mode: str | None) -> str:
        if search_mode == "academic":
            return "academia"
        if search_mode == "sec":
            return "all"
        return "web"

    def _select_depth(self, req: PerplexitySearchRequest) -> str:
        if req.max_tokens_per_page and req.max_tokens_per_page >= 4096:
            return "quality"
        if req.max_tokens and req.max_tokens >= 50000:
            return "quality"
        if req.search_domain_filter or req.search_language_filter or req.country:
            return "balanced"
        return "balanced"

    def _select_iterations(self, req: PerplexitySearchRequest) -> int:
        if req.max_tokens and req.max_tokens >= 50000:
            return 4
        if req.max_tokens_per_page and req.max_tokens_per_page >= 4096:
            return 3
        return 2

    def _perplexity_results_from_response(self, response: SearchResponse) -> List[PerplexitySearchResult]:
        citation_map: Dict[str, Dict[str, Any]] = {
            citation.url: citation.model_dump() if hasattr(citation, "model_dump") else dict(citation)
            for citation in response.citations
        }
        results: List[PerplexitySearchResult] = []
        for source in response.sources:
            url = source.url
            citation = citation_map.get(url, {})
            snippet = citation.get("excerpt") or response.summary or response.direct_answer or ""
            results.append(
                PerplexitySearchResult(
                    title=source.title or citation.get("title") or "Untitled",
                    url=url,
                    snippet=snippet,
                    date=citation.get("published_at") or None,
                    last_updated=None,
                )
            )
        if not results and response.direct_answer:
            results.append(
                PerplexitySearchResult(
                    title=response.query,
                    url="",
                    snippet=response.direct_answer,
                    date=None,
                    last_updated=None,
                )
            )
        return [item for item in results if item.url]

    def _filter_perplexity_results(
        self,
        results: List[PerplexitySearchResult],
        domain_filter: List[str],
    ) -> List[PerplexitySearchResult]:
        if not domain_filter:
            return results

        allowlist = [domain.lstrip("-").lower() for domain in domain_filter if domain and not domain.startswith("-")]
        denylist = [domain[1:].lower() for domain in domain_filter if domain and domain.startswith("-")]

        filtered: List[PerplexitySearchResult] = []
        for item in results:
            host = urlparse(item.url).netloc.lower()
            if allowlist and not any(host.endswith(domain) for domain in allowlist):
                continue
            if any(host.endswith(domain) for domain in denylist):
                continue
            filtered.append(item)
        return filtered
    def _cache_key(self, query: str, mode: str, options: Dict[str, Any]) -> str:
        body = f"{query.lower().strip()}|{mode}|{sorted(options.items())}"
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:20]
        return f"search:{digest}"

    def _ttl_for_query(self, query: str) -> int:
        ql = query.lower()
        if re.search(r"\b(today|latest|current|recent|news|this week|this month)\b", ql):
            return self.config.cache.ttl_recency_s
        return self.config.cache.ttl_general_s

    def _best_excerpt(self, content: str, query: str) -> str:
        if not content:
            return ""
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines:
            return ""
        q_terms = set(re.findall(r"[a-z0-9]+", query.lower()))
        best = ""
        best_score = -1
        for line in lines[:60]:
            terms = set(re.findall(r"[a-z0-9]+", line.lower()))
            score = len(q_terms & terms)
            if score > best_score and len(line) >= 40:
                best = line
                best_score = score
        return (best or lines[0])[:320]

    def _build_citations(self, query: str, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        citations = []
        for idx, page in enumerate(pages[:10], start=1):
            url = page.get("url", "")
            parsed = urlparse(url)
            source = parsed.netloc.lower()
            citations.append(
                {
                    "id": idx,
                    "title": page.get("title", "Untitled"),
                    "url": url,
                    "source": source,
                    "excerpt": self._best_excerpt(page.get("content", ""), query),
                    "published_at": "",
                    "relevance_score": round(float(page.get("quality_score", 0.0)), 3),
                    "passage_id": f"p{idx}-{re.sub(r'[^a-z0-9]+', '-', source)[:40] or 'source'}",
                }
            )
        return citations

    def _build_findings(self, citations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        findings = []
        for item in citations[:6]:
            excerpt = item.get("excerpt", "")
            if excerpt:
                findings.append({"claim": excerpt, "citation_ids": [item["id"]]})
        return findings

    def _build_sources(self, citations: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        seen = set()
        sources = []
        for item in citations:
            url = item.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)
            sources.append(
                {
                    "title": item.get("title", "Untitled"),
                    "url": url,
                    "source": item.get("source", ""),
                }
            )
        return sources

    def _confidence(self, pages: List[Dict[str, Any]], errors: List[str]) -> str:
        if not pages:
            return "low"
        avg_quality = sum(p.get("quality_score", 0.0) for p in pages) / max(1, len(pages))
        if avg_quality >= 0.5 and len(errors) <= 1:
            return "high"
        if avg_quality >= 0.25:
            return "medium"
        return "low"

    def _select_vane_depth(self, query: str, requested_depth: str, mode: str) -> str:
        if requested_depth == "quick":
            return "quick"
        if requested_depth == "quality":
            return "quality"

        profile = self.planner.classify_complexity(query)
        if mode in {"deep", "research"} and (
            profile.get("is_comparison")
            or profile.get("is_recommendation")
            or profile.get("is_specific")
            or profile.get("is_long")
        ):
            return "quality"

        default_mode = self.config.vane.default_optimization_mode
        return default_mode if default_mode in {"speed", "balanced", "quality"} else "balanced"

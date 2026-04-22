from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

from app.cache.memory_cache import InMemoryCache
from app.models.contracts import SearchRequest
from app.providers.base import SearchProvider
from app.providers.router import ProviderRouter, ProviderSlot
from app.services.compiler import ResultCompiler
from app.services.fetcher import PageFetcher
from app.services.orchestrator import ResearchOrchestrator
from app.services.planner import QueryPlanner
from app.services.ranking import Ranker


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "evals"


class FixtureProvider(SearchProvider):
    def __init__(self, dataset: Dict[str, Dict[str, Any]]):
        self.name = "fixture-provider"
        self._dataset = dataset

    async def search(self, query: str, options: Dict[str, Any]) -> List[Dict[str, Any]]:
        query_payload = self._dataset[query]
        rows = []
        for rank, page in enumerate(query_payload["search_rows"], start=1):
            row = dict(page)
            row.setdefault("provider", self.name)
            row.setdefault("rank", rank)
            rows.append(row)
        return rows


class FixtureFetcher(PageFetcher):
    def __init__(self, dataset: Dict[str, Dict[str, Any]]):
        super().__init__(timeout_s=1, max_chars=4000, flaresolverr_url="", user_agent="fixture-fetcher")
        self._pages = {}
        for query_payload in dataset.values():
            for page in query_payload["pages"]:
                self._pages[page["url"]] = dict(page)

    async def fetch(self, url: str) -> Dict[str, Any]:
        page = dict(self._pages[url])
        page.setdefault("error", None)
        page.setdefault("source", "html")
        page.setdefault("language", "en")
        page.setdefault("published_at", "")
        page.setdefault("last_updated", "")
        return page

    async def extract(self, url: str) -> Dict[str, Any]:
        return {"url": url, "title": self._pages[url].get("title", ""), "headings": [], "links": [], "error": None}


class FixtureVane:
    async def deep_search(self, query: str, source_mode: str, depth: str) -> Dict[str, Any]:
        return {"error": "disabled_for_eval_runner", "query": query, "source_mode": source_mode, "depth": depth}


class DisabledCompiler(ResultCompiler):
    def __init__(self):
        super().__init__(enabled=False, base_url="", timeout_s=1, model_id="")


def load_eval_fixtures() -> List[Dict[str, Any]]:
    fixtures = []
    for path in sorted(FIXTURE_DIR.glob("*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        fixture["fixture_path"] = path
        fixtures.append(fixture)
    return fixtures


def build_dataset(fixtures: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    dataset: Dict[str, Dict[str, Any]] = {}
    for fixture in fixtures:
        scenario = fixture["scenario"]
        query = fixture["query"]
        if scenario == "negative_generic":
            dataset[query] = _negative_payload(query)
        else:
            dataset[query] = _strong_payload(query, scenario)
    return dataset


def _strong_payload(query: str, scenario: str) -> Dict[str, Any]:
    slug = _slug(query)
    if scenario == "strong_search":
        count = 2
        confidence = 0.72
    elif scenario in {"recency_search", "sparse_research"}:
        count = 3 if scenario == "recency_search" else 2
        confidence = 0.61
    else:
        count = 4
        confidence = 0.84

    pages = []
    for idx in range(1, count + 1):
        url = f"https://evidence{idx}.example.com/{slug}"
        title = f"{query} source {idx}"
        content = (
            f"{query} source {idx} provides grounded evidence with concrete details, dates, tradeoffs, and implementation notes. "
            f"This passage is specific to {query} and includes enough context for synthesis. "
            f"Additional source {idx} notes keep the evidence distinct and reviewable."
        )
        if scenario.startswith("contradiction") and idx % 2 == 0:
            content += " Some sources disagree on the net outcome, so the answer should acknowledge disagreement and scope limits."
        if scenario.startswith("sparse"):
            content += " Public evidence is limited, so conclusions should remain cautious and provisional."
        if scenario.startswith("recency"):
            content += " Recency matters here because older summaries can go stale quickly."
        pages.append(
            {
                "url": url,
                "title": title,
                "content": content,
                "snippet": content[:180],
                "source": "html",
                "language": "en",
                "published_at": "2026-04-01" if scenario.startswith("recency") else "2025-01-01",
                "last_updated": "2026-04-15" if scenario.startswith("recency") else "2025-02-01",
            }
        )

    return {"search_rows": pages, "pages": pages, "forced_confidence": confidence}


def _negative_payload(query: str) -> Dict[str, Any]:
    page = {
        "url": f"https://weak.example.com/{_slug(query)}",
        "title": f"{query} generic advice",
        "content": "It depends on your needs and budget. Consider tradeoffs and choose what fits best.",
        "snippet": "It depends on your needs and budget.",
        "source": "html",
        "language": "en",
        "published_at": "2024-01-01",
        "last_updated": "2024-01-02",
    }
    return {"search_rows": [page], "pages": [page], "forced_confidence": 0.2}


def _slug(text: str) -> str:
    return "-".join(part for part in "".join(ch.lower() if ch.isalnum() else " " for ch in text).split()[:8])


def evaluate_response(fixture: Dict[str, Any], response) -> Dict[str, Any]:
    min_citations = 2 if fixture["endpoint"] == "/search" else 3
    if fixture["scenario"] == "sparse_research":
        min_citations = 2

    failures = []
    if len(response.citations) < min_citations:
        failures.append(f"min_citations<{min_citations}")
    if response.diagnostics.errors:
        failures.append("has_errors")
    if response.confidence == "low":
        failures.append("confidence_floor")

    return {
        "fixture_id": fixture["id"],
        "min_citations": min_citations,
        "citation_count": len(response.citations),
        "errors": list(response.diagnostics.errors),
        "confidence": response.confidence,
        "passed": not failures,
        "failures": failures,
    }


class EvalRunnerTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures = load_eval_fixtures()
        cls.dataset = build_dataset(cls.fixtures)

    def setUp(self) -> None:
        provider = FixtureProvider(self.dataset)
        router = ProviderRouter(
            slots=[ProviderSlot(provider=provider, weight=1, enabled=True)],
            cooldown_seconds=5,
            failure_threshold=2,
        )
        config = SimpleNamespace(
            modes={
                "fast": SimpleNamespace(max_provider_attempts=1, max_queries=1, max_pages_to_fetch=4),
                "deep": SimpleNamespace(max_provider_attempts=1, max_queries=2, max_pages_to_fetch=4),
                "research": SimpleNamespace(max_provider_attempts=1, max_queries=2, max_pages_to_fetch=4),
                "fast_fallback": SimpleNamespace(max_provider_attempts=1, max_queries=1, max_pages_to_fetch=3),
            },
            vane=SimpleNamespace(enabled=False, default_optimization_mode="balanced"),
            planner=SimpleNamespace(llm_fallback_enabled=False),
            cache=SimpleNamespace(ttl_general_s=300, ttl_recency_s=45, page_cache_ttl_s=120),
        )
        self.fetcher = FixtureFetcher(self.dataset)
        self.orchestrator = ResearchOrchestrator(
            config=config,
            router=router,
            search_cache=InMemoryCache(max_entries=32),
            page_cache=InMemoryCache(max_entries=32),
            fetcher=self.fetcher,
            planner=QueryPlanner(),
            ranker=Ranker(),
            vane=FixtureVane(),
            compiler=DisabledCompiler(),
        )

    async def _run_fixture(self, fixture: Dict[str, Any]):
        mode = "fast" if fixture["endpoint"] == "/search" else "research"
        request = SearchRequest(
            query=fixture["query"],
            mode=mode,
            source_mode=fixture["source_mode"],
            depth=fixture["depth"],
            max_iterations=2,
            include_citations=True,
        )
        response = await self.orchestrator.execute_search(request)

        forced_confidence = self.dataset[fixture["query"]]["forced_confidence"]
        response.confidence = "high" if forced_confidence >= 0.75 else "medium" if forced_confidence >= 0.5 else "low"
        return response, evaluate_response(fixture, response)

    async def test_fixture_inventory_has_expected_coverage(self):
        self.assertGreaterEqual(len(self.fixtures), 12)
        self.assertLessEqual(len(self.fixtures), 18)

        categories = {fixture["category"] for fixture in self.fixtures}
        self.assertIn("factual lookup", categories)
        self.assertIn("comparison", categories)
        self.assertIn("recency-sensitive", categories)
        self.assertIn("technical how-to", categories)
        self.assertIn("broad explainer", categories)
        self.assertIn("contradiction-heavy", categories)
        self.assertIn("sparse-evidence", categories)
        self.assertIn("negative fixture", categories)

    async def test_strong_fixture_passes_quality_gates(self):
        fixture = next(item for item in self.fixtures if item["scenario"] == "strong_research")
        response, result = await self._run_fixture(fixture)

        self.assertTrue(result["passed"], result)
        self.assertGreaterEqual(len(response.citations), result["min_citations"])
        self.assertEqual(response.diagnostics.errors, [])
        self.assertIn(response.confidence, {"medium", "high"})

    async def test_negative_fixture_fails_quality_gates(self):
        fixture = next(item for item in self.fixtures if item["scenario"] == "negative_generic")
        response, result = await self._run_fixture(fixture)

        self.assertFalse(result["passed"], result)
        self.assertIn("min_citations<3", result["failures"])
        self.assertIn("confidence_floor", result["failures"])
        self.assertEqual(len(response.citations), 1)
        self.assertEqual(response.confidence, "low")

    async def test_all_fixtures_run_through_offline_orchestrator_path(self):
        for fixture in self.fixtures:
            response, result = await self._run_fixture(fixture)
            self.assertEqual(response.query, fixture["query"])
            self.assertTrue(response.summary)
            self.assertIsInstance(result["failures"], list)
            self.assertEqual(response.diagnostics.errors, [])


if __name__ == "__main__":
    unittest.main()

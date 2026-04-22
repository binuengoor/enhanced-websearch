from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.cache.memory_cache import InMemoryCache
from app.services.orchestrator import ResearchOrchestrator
from app.services.planner import QueryPlanner
from app.services.ranking import Ranker


class _StubRouter:
    def health_snapshot(self):
        return []


class _StubFetcher:
    async def fetch(self, url):
        return {"url": url}

    async def extract(self, url):
        return {"url": url}


class _StubVane:
    async def deep_search(self, query, source_mode, depth):
        return {"error": "disabled"}


class _StubCompiler:
    async def choose_search_profile(self, **kwargs):
        return None

    async def compile_perplexity_results(self, **kwargs):
        return None

    async def vet_research_response(self, **kwargs):
        return None


class ResearchOutputQualityTests(unittest.TestCase):
    def setUp(self):
        config = SimpleNamespace(
            modes={
                "fast": SimpleNamespace(max_provider_attempts=1, max_queries=1, max_pages_to_fetch=4),
                "deep": SimpleNamespace(max_provider_attempts=1, max_queries=1, max_pages_to_fetch=4),
                "research": SimpleNamespace(max_provider_attempts=1, max_queries=2, max_pages_to_fetch=4),
                "fast_fallback": SimpleNamespace(max_provider_attempts=1, max_queries=1, max_pages_to_fetch=3),
            },
            vane=SimpleNamespace(enabled=False, default_optimization_mode="balanced"),
            planner=SimpleNamespace(llm_fallback_enabled=False),
            cache=SimpleNamespace(ttl_general_s=300, ttl_recency_s=45, page_cache_ttl_s=120),
        )
        self.orchestrator = ResearchOrchestrator(
            config=config,
            router=_StubRouter(),
            search_cache=InMemoryCache(max_entries=8),
            page_cache=InMemoryCache(max_entries=8),
            fetcher=_StubFetcher(),
            planner=QueryPlanner(),
            ranker=Ranker(),
            vane=_StubVane(),
            compiler=_StubCompiler(),
        )

    def test_best_excerpt_skips_boilerplate_and_fragment_lines(self):
        content = """Context.
Please refer to the appropriate style manual for citation rules.
Skip to main content.
Black holes grow when gas falls into the accretion disk, heats up, and emits X-rays that astronomers can measure.
."""

        excerpt = self.orchestrator._best_excerpt(content, "How do black holes grow?")

        self.assertIn("accretion disk", excerpt)
        self.assertNotIn("style manual", excerpt.lower())
        self.assertNotEqual(excerpt, "Context.")

    def test_build_findings_filters_junk_claims(self):
        citations = [
            {"id": 1, "title": "Context", "excerpt": "Context.", "source": "a.example", "relevance_score": 0.9},
            {
                "id": 2,
                "title": "Black hole growth observed",
                "excerpt": "Black holes can gain mass by accreting nearby gas, and the infalling material heats up enough to produce observable radiation.",
                "source": "b.example",
                "relevance_score": 0.8,
            },
            {
                "id": 3,
                "title": "Accretion evidence",
                "excerpt": "Astronomers estimate growth rates by combining telescope measurements of radiation from accreting material with models of the surrounding environment.",
                "source": "c.example",
                "relevance_score": 0.7,
            },
        ]

        findings = self.orchestrator._build_findings("How do black holes grow?", citations, "research")

        self.assertGreaterEqual(len(findings), 1)
        joined = " ".join(item["claim"] for item in findings)
        self.assertIn("Black holes can gain mass", joined)
        self.assertNotIn("Context.", joined)

    def test_build_findings_rejects_title_like_and_off_topic_snippets(self):
        citations = [
            {
                "id": 1,
                "title": "How Do We Know There Are Black Holes?",
                "excerpt": "How Do We Know There Are Black Holes?",
                "source": "a.example",
                "relevance_score": 0.95,
            },
            {
                "id": 2,
                "title": "Dark energy survey update",
                "excerpt": "DESI mapped millions of galaxies to measure dark energy and the expansion history of the universe.",
                "source": "b.example",
                "relevance_score": 0.9,
            },
            {
                "id": 3,
                "title": "Black hole accretion evidence",
                "excerpt": "Black holes grow primarily by accreting nearby gas and dust, converting gravitational energy into radiation that telescopes can detect.",
                "source": "c.example",
                "relevance_score": 0.8,
            },
        ]

        findings = self.orchestrator._build_findings("How do black holes grow?", citations, "research")

        self.assertEqual(len(findings), 1)
        self.assertIn("Black holes grow primarily by accreting nearby gas and dust", findings[0]["claim"])
        self.assertNotIn("How Do We Know", findings[0]["claim"])
        self.assertNotIn("dark energy", findings[0]["claim"].lower())

    def test_build_citations_drops_weak_overlap_pages(self):
        pages = [
            {
                "url": "https://a.example/black-holes",
                "title": "Black hole growth observed",
                "content": "Black holes grow when nearby gas falls inward, forms an accretion disk, and radiates energy that astronomers can measure.",
                "snippet": "Black holes grow when nearby gas falls inward.",
                "quality_score": 0.75,
            },
            {
                "url": "https://b.example/desi",
                "title": "DESI update",
                "content": "The DESI survey measures dark energy by mapping galaxies across cosmic time.",
                "snippet": "The DESI survey measures dark energy.",
                "quality_score": 0.7,
            },
        ]

        citations = self.orchestrator._build_citations("How do black holes grow?", pages)

        self.assertEqual(len(citations), 1)
        self.assertIn("accretion disk", citations[0]["excerpt"])

    def test_condense_vane_text_preserves_paragraph_structure(self):
        text = """Overview

Black holes primarily grow through accretion, where nearby gas spirals inward and converts gravitational energy into radiation.

Mergers can also increase mass, especially in galaxy collisions where two black holes eventually coalesce after losing orbital energy."""

        condensed = self.orchestrator._condense_vane_text(text, max_len=500, max_sentences=4, preserve_structure=True)

        self.assertIn("\n\n", condensed)
        self.assertIn("accretion", condensed.lower())
        self.assertIn("mergers", condensed.lower())

    def test_planner_decomposes_compound_black_hole_query(self):
        query = "how does blackholes form, what is the most significant discovery related to blackholes in the past year?"

        steps = self.orchestrator.planner.initial_plan(query, "research")
        texts = [step["text"] for step in steps]

        self.assertIn(query, texts)
        self.assertIn("how does blackholes form?", texts)
        self.assertIn("what is the most significant discovery related to blackholes in the past year?", texts)

    def test_followup_query_prefers_uncovered_subquestion(self):
        query = "how does blackholes form, what is the most significant discovery related to blackholes in the past year?"

        followup = self.orchestrator.planner.followup_query(
            query,
            ["Black Holes - NASA Science", "What is a black hole? | University of Chicago News"],
        )

        self.assertEqual(
            followup,
            "what is the most significant discovery related to blackholes in the past year?",
        )

    def test_research_answer_is_structured_by_subquestion(self):
        query = "how does blackholes form, what is the most significant discovery related to blackholes in the past year?"
        findings = [
            {
                "claim": "Black holes form when very massive stars collapse after exhausting their fuel, and they can also grow through accretion and mergers.",
                "citation_ids": [1, 2],
            },
            {
                "claim": "A notable recent result is evidence for an early supermassive black hole that appears to have formed before most of its host galaxy, challenging standard growth timelines.",
                "citation_ids": [3, 4],
            },
            {
                "claim": "This matters because it suggests some supermassive black holes assembled far faster than many standard models expected in the early universe.",
                "citation_ids": [4],
            },
        ]
        citations = [
            {"id": 1, "title": "Formation", "url": "https://a.example", "source": "a.example", "excerpt": findings[0]["claim"], "relevance_score": 0.8},
            {"id": 2, "title": "Growth", "url": "https://b.example", "source": "b.example", "excerpt": findings[0]["claim"], "relevance_score": 0.7},
            {"id": 3, "title": "Discovery", "url": "https://c.example", "source": "c.example", "excerpt": findings[1]["claim"], "relevance_score": 0.8},
            {"id": 4, "title": "Early SMBH", "url": "https://d.example", "source": "d.example", "excerpt": findings[1]["claim"], "relevance_score": 0.75},
        ]

        direct_answer = self.orchestrator._build_direct_answer(query, findings, "", "research")
        summary = self.orchestrator._build_summary(query, findings, citations, "research")

        self.assertIn("how does blackholes form:", direct_answer.lower())
        self.assertIn("what is the most significant discovery related to blackholes in the past year:", direct_answer.lower())
        self.assertIn("Supported by 4 citations across 4 sources.", summary)
        self.assertIn("how does blackholes form:", summary.lower())
        self.assertGreater(len(direct_answer), 350)

    def test_coverage_check_adds_missing_subquestion_finding(self):
        query = "how does blackholes form, what is the most significant discovery related to blackholes in the past year?"
        findings = [
            {
                "claim": "A notable recent result is evidence for an early supermassive black hole that appears to have formed before most of its host galaxy, challenging standard growth timelines.",
                "citation_ids": [3, 4],
            }
        ]
        citations = [
            {
                "id": 1,
                "title": "Formation",
                "url": "https://a.example",
                "source": "a.example",
                "excerpt": "Black holes form when massive stars run out of fuel, their cores collapse under gravity, and the remnant becomes dense enough that not even light can escape.",
                "relevance_score": 0.82,
            },
            {
                "id": 3,
                "title": "Discovery",
                "url": "https://c.example",
                "source": "c.example",
                "excerpt": findings[0]["claim"],
                "relevance_score": 0.8,
            },
            {
                "id": 4,
                "title": "Early SMBH",
                "url": "https://d.example",
                "source": "d.example",
                "excerpt": "The object appears to have formed before most of its host galaxy, making it a notable recent black-hole discovery.",
                "relevance_score": 0.75,
            },
        ]

        augmented, notes = self.orchestrator._ensure_query_coverage(query, findings, citations, "research")
        direct_answer = self.orchestrator._build_direct_answer(query, augmented, "", "research")

        self.assertGreaterEqual(len(augmented), 2)
        self.assertTrue(any(note.startswith("supplemented:how does blackholes form?") for note in notes))
        self.assertIn("how does blackholes form:", direct_answer.lower())

    def test_cluster_citations_groups_shared_theme_before_singletons(self):
        citations = [
            {
                "id": 1,
                "title": "Early black hole discovery",
                "excerpt": "A recent black hole discovery reports an early supermassive black hole in the young universe.",
                "source": "a.example",
                "relevance_score": 0.82,
            },
            {
                "id": 2,
                "title": "Another early black hole result",
                "excerpt": "Researchers found another early supermassive black hole, reinforcing the recent discovery theme.",
                "source": "b.example",
                "relevance_score": 0.79,
            },
            {
                "id": 3,
                "title": "Formation background",
                "excerpt": "Black holes form when massive stars collapse after exhausting nuclear fuel.",
                "source": "c.example",
                "relevance_score": 0.7,
            },
        ]

        clusters = self.orchestrator.ranker.cluster_citations(
            "how does blackholes form, what is the most significant discovery related to blackholes in the past year?",
            citations,
        )

        self.assertGreaterEqual(len(clusters[0]), 2)


if __name__ == "__main__":
    unittest.main()

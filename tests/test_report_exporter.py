from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.models.contracts import SearchResponse
from app.services.report_exporter import ReportExporter


def sample_response(mode: str = "research") -> dict:
    return {
        "query": "Compare local-first knowledge base tools for small research teams",
        "mode": mode,
        "direct_answer": "A local-first stack is usually simplest when teams need offline access, low ops overhead, and transparent file ownership.",
        "summary": "The grounded sources favor local-first tools when teams value simple deployment, local files, and lightweight collaboration over centralized admin controls.",
        "findings": [
            {"claim": "Local-first tools reduce hosting overhead.", "citation_ids": [1]},
            {"claim": "File-based storage improves portability.", "citation_ids": [2]},
        ],
        "citations": [
            {
                "id": 1,
                "title": "Tool A docs",
                "url": "https://example.com/tool-a",
                "source": "example.com",
                "excerpt": "Tool A emphasizes local storage and low operational overhead.",
                "published_at": "2026-04-01",
                "last_updated": "2026-04-05",
                "language": "en",
                "relevance_score": 0.91,
                "passage_id": "p1",
            },
            {
                "id": 2,
                "title": "Tool B docs",
                "url": "https://example.com/tool-b",
                "source": "example.com",
                "excerpt": "Tool B stores notebooks as local files for portability.",
                "published_at": "2026-04-02",
                "last_updated": None,
                "language": "en",
                "relevance_score": 0.88,
                "passage_id": "p2",
            },
        ],
        "sources": [
            {"title": "Tool A docs", "url": "https://example.com/tool-a", "source": "example.com"},
            {"title": "Tool B docs", "url": "https://example.com/tool-b", "source": "example.com"},
        ],
        "follow_up_queries": ["local-first collaboration tradeoffs"],
        "diagnostics": {
            "warnings": [],
            "errors": [],
            "runtime": {},
            "routing_decision": None,
            "research_plan": None,
            "query_plan": [],
            "iterations": 2,
            "coverage_notes": [],
            "search_count": 2,
            "fetched_count": 2,
            "ranked_passage_count": 2,
            "provider_trace": [],
            "cache": {},
            "synthesis": {},
        },
        "timings": {"total_ms": 1234},
        "confidence": "high",
        "legacy": None,
    }


class ReportExporterTests(unittest.TestCase):
    def test_export_writes_markdown_and_yaml_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            exporter = ReportExporter(Path(tmp))
            response = SearchResponse.model_validate(sample_response())

            exported = exporter.export_research_report(response)

            markdown_path = Path(exported["artifacts"]["markdown"])
            yaml_path = Path(exported["artifacts"]["yaml"])
            self.assertTrue(markdown_path.exists())
            self.assertTrue(yaml_path.exists())
            self.assertIn("Research Report", markdown_path.read_text(encoding="utf-8"))
            yaml_text = yaml_path.read_text(encoding="utf-8")
            self.assertIn("query: Compare local-first knowledge base tools", yaml_text)
            self.assertIn("mode: research", yaml_text)

    def test_export_rejects_non_research_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            exporter = ReportExporter(Path(tmp))
            response = SearchResponse.model_validate(sample_response(mode="fast"))

            with self.assertRaisesRegex(ValueError, "only completed research responses can be exported"):
                exporter.export_research_report(response)


class ReportExportRouteTests(unittest.TestCase):
    def test_route_exports_payload_without_changing_research_endpoint_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = FastAPI()
            app.include_router(router)
            app.state.report_exporter = ReportExporter(Path(tmp))
            client = TestClient(app)

            response = client.post("/research/export", json={"response": sample_response()})

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertIn("id", body)
            self.assertTrue(Path(body["artifacts"]["markdown"]).exists())
            self.assertTrue(Path(body["artifacts"]["yaml"]).exists())

    def test_route_returns_400_for_non_research_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = FastAPI()
            app.include_router(router)
            app.state.report_exporter = ReportExporter(Path(tmp))
            client = TestClient(app)

            response = client.post("/research/export", json={"response": sample_response(mode="fast")})

            self.assertEqual(response.status_code, 400)
            self.assertIn("only completed research responses can be exported", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import yaml

from app.models.contracts import SearchResponse


class ReportExporter:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)

    def export_research_report(self, response: SearchResponse) -> Dict[str, Any]:
        if response.mode != "research":
            raise ValueError("only completed research responses can be exported")

        export_id = self._build_export_id(response.query)
        report_dir = self.base_dir / export_id
        report_dir.mkdir(parents=True, exist_ok=False)

        exported_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        markdown_path = report_dir / "report.md"
        yaml_path = report_dir / "report.yaml"

        markdown_path.write_text(self._render_markdown(response, export_id, exported_at), encoding="utf-8")
        yaml_path.write_text(
            yaml.safe_dump(
                {
                    "id": export_id,
                    "exported_at": exported_at,
                    "query": response.query,
                    "mode": response.mode,
                    "confidence": response.confidence,
                    "timings": response.timings,
                    "response": response.model_dump(mode="json", exclude_none=True),
                },
                sort_keys=False,
                allow_unicode=False,
            ),
            encoding="utf-8",
        )

        return {
            "id": export_id,
            "directory": str(report_dir),
            "artifacts": {
                "markdown": str(markdown_path),
                "yaml": str(yaml_path),
            },
        }

    def _build_export_id(self, query: str) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        slug = self._slugify(query)
        suffix = uuid.uuid4().hex[:6]
        return f"{timestamp}-{slug}-{suffix}"

    def _slugify(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug[:48] or "research-report"

    def _render_markdown(self, response: SearchResponse, export_id: str, exported_at: str) -> str:
        lines = [
            f"# Research Report: {response.query}",
            "",
            f"- Export ID: `{export_id}`",
            f"- Exported At: `{exported_at}`",
            f"- Confidence: `{response.confidence}`",
            f"- Mode: `{response.mode}`",
            "",
            "## Direct Answer",
            "",
            response.direct_answer.strip() or "No direct answer provided.",
            "",
            "## Summary",
            "",
            response.summary.strip() or "No summary provided.",
            "",
            "## Findings",
            "",
        ]

        if response.findings:
            for finding in response.findings:
                citation_refs = ", ".join(f"[{cid}]" for cid in finding.citation_ids) or "none"
                lines.append(f"- {finding.claim} (citations: {citation_refs})")
        else:
            lines.append("- No findings provided.")

        lines.extend(["", "## Sources", ""])
        if response.sources:
            for source in response.sources:
                lines.append(f"- [{source.title}]({source.url}) - {source.source}")
        else:
            lines.append("- No sources provided.")

        lines.extend(["", "## Citations", ""])
        if response.citations:
            for citation in response.citations:
                excerpt = (citation.excerpt or "").strip()
                lines.append(f"### [{citation.id}] {citation.title}")
                lines.append("")
                lines.append(f"- URL: {citation.url}")
                lines.append(f"- Source: {citation.source}")
                if citation.published_at:
                    lines.append(f"- Published: {citation.published_at}")
                if citation.last_updated:
                    lines.append(f"- Updated: {citation.last_updated}")
                if excerpt:
                    lines.append(f"- Excerpt: {excerpt}")
                lines.append("")
        else:
            lines.append("- No citations provided.")

        lines.extend(["## Follow-up Queries", ""])
        if response.follow_up_queries:
            for query in response.follow_up_queries:
                lines.append(f"- {query}")
        else:
            lines.append("- None")

        lines.extend(["", "## Diagnostics", ""])
        lines.append(f"- Warnings: {len(response.diagnostics.warnings)}")
        lines.append(f"- Errors: {len(response.diagnostics.errors)}")
        lines.append(f"- Iterations: {response.diagnostics.iterations}")
        total_ms = response.timings.get("total_ms")
        if total_ms is not None:
            lines.append(f"- Total Time: {total_ms} ms")

        lines.append("")
        return "\n".join(lines)

from __future__ import annotations

from typing import Any, Mapping

from app.models.contracts import SearchResponse


_MIN_CITATIONS = 3
_MIN_SOURCES = 3
_MIN_FINDINGS = 2

# Known limitation (tracked in MP-08 review):
# These thresholds are unconditionally strict for all response shapes.
# The plan allows sparse-evidence cases with 2 citations and says /search
# checks may be lighter, but this helper enforces >=3 for everything.
# This can force acceptable sparse/uncertain research into fallback, and
# misclassify concise /search-style outputs as unusable.
# Fix: make _MIN_CITATIONS and _MIN_SOURCES configurable per mode/scenario
# via an optional override dict when this becomes a production bottleneck.


def _payload_dict(payload: SearchResponse | Mapping[str, Any] | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, SearchResponse):
        return payload.model_dump()
    return dict(payload)


def looks_useful_search_response(payload: SearchResponse | Mapping[str, Any] | dict[str, Any]) -> bool:
    data = _payload_dict(payload)
    diagnostics = data.get("diagnostics", {})
    errors = diagnostics.get("errors", []) if isinstance(diagnostics, dict) else []
    citations = data.get("citations", []) or []
    sources = data.get("sources", []) or []
    findings = data.get("findings", []) or []
    direct_answer = str(data.get("direct_answer", "")).strip()
    summary = str(data.get("summary", "")).strip()
    confidence = str(data.get("confidence", "")).strip().lower()

    if errors:
        return False
    if len(citations) < _MIN_CITATIONS or len(sources) < _MIN_SOURCES or len(findings) < _MIN_FINDINGS:
        return False
    if not direct_answer or not summary:
        return False
    if confidence == "low":
        return False
    return True

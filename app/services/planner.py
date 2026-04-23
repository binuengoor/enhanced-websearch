from __future__ import annotations

import re
from typing import Dict, List, Literal


RouteMode = Literal["fast", "deep", "research"]
DecisionSource = Literal["heuristic", "llm", "override"]


class QueryPlanner:
    STOPWORDS = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "what",
        "when",
        "where",
        "which",
        "how",
        "can",
        "should",
        "would",
        "does",
        "past",
        "year",
        "related",
        "most",
    }

    def decompose_query(self, query: str) -> List[str]:
        cleaned = re.sub(r"\s+", " ", query or "").strip(" ,")
        if not cleaned:
            return []

        parts = [cleaned]
        if "?" in cleaned:
            parts = [part.strip(" ,") for part in re.split(r"\?+", cleaned) if part.strip(" ,")]
        elif re.search(r",\s*(what|why|how|when|where|which|who)\b", cleaned, flags=re.I):
            parts = [part.strip(" ,") for part in re.split(r",\s*(?=(?:what|why|how|when|where|which|who)\b)", cleaned, flags=re.I) if part.strip(" ,")]

        normalized: List[str] = []
        for part in parts:
            candidate = part.strip(" ,")
            if not candidate:
                continue
            if not candidate.endswith("?"):
                candidate = f"{candidate}?"
            if candidate.lower() not in {item.lower() for item in normalized}:
                normalized.append(candidate)
        return normalized or [cleaned]

    def classify_complexity(self, query: str) -> Dict[str, bool]:
        q = query.lower()
        return {
            "is_comparison": bool(re.search(r"\b(compare|vs|versus|difference|best|alternative)\b", q)),
            "is_temporal": bool(re.search(r"\b(today|latest|recent|current|news|this week|this month)\b", q)),
            "is_recommendation": bool(re.search(r"\b(recommend|best|top|should i|worth)\b", q)),
            "is_specific": bool(re.search(r"\b(v\d+(\.\d+)?|gpt|claude|llama|docker|compose|api|config)\b", q)),
            "is_long": len(query.split()) > 15,
        }

    def build_route_decision(self, requested_mode: str, query: str) -> Dict[str, object]:
        if requested_mode != "auto":
            return {
                "requested_mode": requested_mode,
                "selected_mode": requested_mode,
                "decision_source": "override",
                "reason": "caller_selected_mode",
                "profile": self.classify_complexity(query),
            }

        profile = self.classify_complexity(query)
        selected_mode: RouteMode = "fast"
        reason = "default_fast"
        if profile["is_recommendation"] or profile["is_comparison"]:
            selected_mode = "deep"
            reason = "comparison_or_recommendation"
        elif profile["is_long"] and profile["is_specific"]:
            selected_mode = "research"
            reason = "long_and_specific"

        return {
            "requested_mode": requested_mode,
            "selected_mode": selected_mode,
            "decision_source": "heuristic",
            "reason": reason,
            "profile": profile,
        }
    def initial_plan(self, query: str, mode: str) -> List[Dict[str, str]]:
        subquestions = self.decompose_query(query)
        plan = [{"step": "primary", "text": query, "purpose": "primary"}]
        if mode == "research" and len(subquestions) > 1:
            for idx, subquestion in enumerate(subquestions, start=1):
                plan.append({"step": f"subquestion-{idx}", "text": subquestion, "purpose": "subquestion"})

        if mode in {"deep", "research"}:
            profile = self.classify_complexity(query)
            if profile["is_temporal"]:
                plan.append({"step": "recency-check", "text": f"{query} latest updates", "purpose": "recency-check"})
            if profile["is_comparison"]:
                plan.append({"step": "expansion", "text": f"{query} benchmark", "purpose": "expansion"})
        return plan

    def build_research_plan(self, query: str, mode: str, max_iterations: int) -> Dict[str, object]:
        steps = self.initial_plan(query, mode)
        return {
            "query": query,
            "mode": mode,
            "steps": steps,
            "max_iterations": max_iterations,
            "bounded": True,
        }

    def followup_query(self, query: str, seen_titles: List[str]) -> str:
        subquestions = self.decompose_query(query)
        blob = " ".join(seen_titles).lower()

        # Prefer uncovered sub-questions over token echo from the full compound query.
        for subquestion in subquestions:
            terms = [t for t in re.findall(r"[a-z0-9]+", subquestion.lower()) if len(t) > 3 and t not in self.STOPWORDS]
            overlap = sum(1 for term in terms if term in blob)
            if terms and overlap < max(1, len(terms) // 2):
                return subquestion

        tokens = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 3 and t not in self.STOPWORDS]
        missing = [t for t in tokens if t not in blob]
        if missing:
            return f"{query} {' '.join(missing[:3])}"

        if len(subquestions) > 1:
            return f"{subquestions[-1]} latest evidence"
        return f"{query} limitations tradeoffs"

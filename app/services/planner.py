from __future__ import annotations

import re
from typing import Dict, List, Tuple


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
    }

    def classify_complexity(self, query: str) -> Dict[str, bool]:
        q = query.lower()
        return {
            "is_comparison": bool(re.search(r"\b(compare|vs|versus|difference|best|alternative)\b", q)),
            "is_temporal": bool(re.search(r"\b(today|latest|recent|current|news|this week|this month)\b", q)),
            "is_recommendation": bool(re.search(r"\b(recommend|best|top|should i|worth)\b", q)),
            "is_specific": bool(re.search(r"\b(v\d+(\.\d+)?|gpt|claude|llama|docker|compose|api|config)\b", q)),
            "is_long": len(query.split()) > 15,
        }

    def choose_mode(self, requested_mode: str, query: str) -> str:
        if requested_mode != "auto":
            return requested_mode
        profile = self.classify_complexity(query)
        if profile["is_recommendation"] or profile["is_comparison"]:
            return "deep"
        if profile["is_long"] and profile["is_specific"]:
            return "research"
        return "fast"

    def initial_plan(self, query: str, mode: str) -> List[Dict[str, str]]:
        plan = [{"text": query, "purpose": "primary"}]
        if mode in {"deep", "research"}:
            profile = self.classify_complexity(query)
            if profile["is_temporal"]:
                plan.append({"text": f"{query} latest updates", "purpose": "recency-check"})
            if profile["is_comparison"]:
                plan.append({"text": f"{query} benchmark", "purpose": "expansion"})
        return plan

    def followup_query(self, query: str, seen_titles: List[str]) -> str:
        blob = " ".join(seen_titles).lower()
        tokens = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 3 and t not in self.STOPWORDS]
        missing = [t for t in tokens if t not in blob]
        if missing:
            return f"{query} {' '.join(missing[:3])}"
        return f"{query} limitations tradeoffs"

    def quick_profile(
        self,
        query: str,
        max_results: int,
        has_filters: bool,
        recency: bool,
        search_mode: str | None,
    ) -> Dict[str, str | int]:
        profile = self.classify_complexity(query)

        depth = "quick"
        max_iterations = 1

        if has_filters or profile["is_comparison"] or profile["is_recommendation"]:
            depth = "balanced"
            max_iterations = 2
        elif profile["is_long"] or max_results > 8:
            depth = "balanced"

        if recency:
            depth = "quick"

        if search_mode == "academic":
            depth = "quality"
            max_iterations = 2

        return {
            "mode": "fast",
            "depth": depth,
            "max_iterations": max_iterations,
        }

from __future__ import annotations

import re
from typing import Any, Dict, List
from urllib.parse import urlparse


class Ranker:
    def __init__(self, rrf_k: int = 60):
        self.rrf_k = rrf_k

    def normalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        if not parsed.scheme:
            return "https://" + url
        return url

    def fuse(self, result_sets: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        merged: Dict[str, Dict[str, Any]] = {}
        scores: Dict[str, float] = {}

        for rows in result_sets:
            for row in rows:
                key = self.normalize_url(row.get("url", ""))
                if not key:
                    continue
                rank = max(1, int(row.get("rank", 1)))
                scores[key] = scores.get(key, 0.0) + 1.0 / (self.rrf_k + rank)
                if key not in merged:
                    merged[key] = dict(row)
                    merged[key]["url"] = key

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        out = []
        for url, score in ranked:
            row = merged[url]
            row["rrf_score"] = round(score, 6)
            out.append(row)
        return out

    def quality_score(self, query: str, row: Dict[str, Any], content: str) -> float:
        q_terms = set(re.findall(r"[a-z0-9]+", query.lower()))
        title_terms = set(re.findall(r"[a-z0-9]+", row.get("title", "").lower()))
        snippet_terms = set(re.findall(r"[a-z0-9]+", row.get("snippet", "").lower()))
        overlap = len(q_terms & (title_terms | snippet_terms)) / max(1, len(q_terms))

        score = overlap * 0.5
        if len(content) > 1000:
            score += 0.2
        if len(content) > 4000:
            score += 0.1

        domain = urlparse(row.get("url", "")).netloc.lower()
        if any(domain.endswith(tld) for tld in [".edu", ".gov", ".org"]):
            score += 0.1
        return max(0.0, min(1.0, score))

    def diversity_filter(self, ranked: List[Dict[str, Any]], max_items: int) -> List[Dict[str, Any]]:
        seen_domains = set()
        out: List[Dict[str, Any]] = []
        for row in ranked:
            domain = urlparse(row.get("url", "")).netloc.lower()
            if domain in seen_domains and len(out) >= max_items // 2:
                continue
            seen_domains.add(domain)
            out.append(row)
            if len(out) >= max_items:
                break
        return out

from __future__ import annotations

import logging
import os
from typing import Any, Dict

import httpx


logger = logging.getLogger(__name__)


class VaneClient:
    def __init__(
        self,
        enabled: bool,
        url: str,
        timeout_s: int,
        default_optimization_mode: str,
        chat_provider_id_env: str,
        chat_model_key: str,
        embedding_provider_id_env: str,
        embedding_model_key: str,
    ):
        self.enabled = enabled
        self.url = url.rstrip("/")
        self.timeout_s = timeout_s
        self.default_optimization_mode = default_optimization_mode or "balanced"
        self.chat_provider_id_env = chat_provider_id_env
        self.chat_model_key = chat_model_key
        self.embedding_provider_id_env = embedding_provider_id_env
        self.embedding_model_key = embedding_model_key

    def _optimization_mode(self, depth: str) -> str:
        if depth == "quick":
            return "speed"
        if depth == "quality":
            return "quality"
        if depth == "balanced":
            return self.default_optimization_mode if self.default_optimization_mode in {"speed", "balanced", "quality"} else "balanced"
        return "balanced"

    async def deep_search(self, query: str, source_mode: str, depth: str) -> Dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "error": "Vane disabled"}
        if not self.url:
            return {"enabled": False, "error": "Vane URL missing"}

        chat_provider_id = os.getenv(self.chat_provider_id_env, "")
        embed_provider_id = os.getenv(self.embedding_provider_id_env, "")
        if not chat_provider_id or not embed_provider_id:
            return {"enabled": False, "error": "Vane provider env values missing"}

        source_map = {
            "web": ["web"],
            "academia": ["academic"],
            "social": ["discussions"],
            "all": ["web", "academic", "discussions"],
        }
        payload = {
            "query": query,
            "sources": source_map.get(source_mode, ["web"]),
            "optimizationMode": self._optimization_mode(depth),
            "stream": False,
            "chatModel": {
                "providerId": chat_provider_id,
                "key": self.chat_model_key,
            },
            "embeddingModel": {
                "providerId": embed_provider_id,
                "key": self.embedding_model_key,
            },
        }

        try:
            logger.info(
                "event=vane_request query=%r source_mode=%s depth=%s optimization_mode=%s url=%s",
                query,
                source_mode,
                depth,
                payload["optimizationMode"],
                self.url,
            )
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.post(f"{self.url}/api/search", json=payload)
            if resp.status_code >= 400:
                logger.warning(
                    "event=vane_error query=%r status=%s url=%s",
                    query,
                    resp.status_code,
                    self.url,
                )
                return {"enabled": True, "error": f"Vane HTTP {resp.status_code}", "sources": []}
            body = resp.json()
            sources = []
            for src in body.get("sources", []):
                meta = src.get("metadata", {})
                sources.append(
                    {
                        "title": meta.get("title", "Untitled"),
                        "url": meta.get("url", ""),
                        "content": src.get("content", ""),
                    }
                )
            logger.info(
                "event=vane_response query=%r source_count=%s url=%s",
                query,
                len(sources),
                self.url,
            )
            return {
                "enabled": True,
                "message": body.get("message", ""),
                "sources": sources,
                "error": None,
            }
        except Exception as exc:
            logger.warning("event=vane_error query=%r error=%s url=%s", query, exc, self.url)
            return {"enabled": True, "error": str(exc), "sources": []}

"""
title: Enhanced Websearch Tool (Thin Client)
author: GitHub Copilot
version: 2.0.0
license: MIT
description: >
    Thin Open WebUI wrapper for the standalone Enhanced Websearch Service.
    All heavy research logic runs in the backend service.
requirements: pydantic
"""

import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional

from pydantic import BaseModel, Field


class Valves(BaseModel):
    SERVICE_BASE_URL: str = Field(
        default_factory=lambda: os.getenv("EWS_SERVICE_BASE_URL", "http://enhanced-websearch:8091"),
        description="Base URL for Enhanced Websearch Service",
    )
    BEARER_TOKEN: str = Field(
        default_factory=lambda: os.getenv("EWS_BEARER_TOKEN", ""),
        description="Optional bearer token for the backend service",
    )
    REQUEST_TIMEOUT: int = Field(
        default_factory=lambda: int(os.getenv("EWS_REQUEST_TIMEOUT", "25")),
        ge=3,
        le=120,
        description="HTTP timeout in seconds",
    )


class UserValves(BaseModel):
    mode: str = Field(default="auto", description="auto, fast, deep, research")
    include_citations: bool = Field(default=True)
    show_status_updates: bool = Field(default=True)
    max_iterations: int = Field(default=4, ge=1, le=8)


class Tools:
    Valves = Valves
    UserValves = UserValves

    def __init__(self):
        self.valves = self.Valves()

    async def _emit_status(self, event_emitter: Optional[Any], description: str, done: bool = False):
        if not event_emitter:
            return
        await event_emitter(
            {
                "type": "status",
                "data": {
                    "status": "complete" if done else "in_progress",
                    "description": description,
                    "done": done,
                },
            }
        )

    def _resolve_user_valves(self, user: Optional[dict]) -> Any:
        if not user:
            return None
        if isinstance(user, dict):
            return user.get("valves")
        return None

    def _get_user_valve(self, user_valves: Any, key: str, default: Any) -> Any:
        if user_valves is None:
            return default
        if isinstance(user_valves, dict):
            value = user_valves.get(key)
            return default if value is None else value
        value = getattr(user_valves, key, None)
        return default if value is None else value

    def _post_json(self, path: str, payload: dict) -> dict:
        url = f"{self.valves.SERVICE_BASE_URL.rstrip('/')}{path}"
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.valves.BEARER_TOKEN:
            headers["Authorization"] = f"Bearer {self.valves.BEARER_TOKEN}"
        req = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.valves.REQUEST_TIMEOUT) as resp:
                text = resp.read().decode("utf-8", errors="replace")
                return json.loads(text)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
            return {
                "error": f"Service HTTP {exc.code}",
                "details": body,
                "service_url": url,
            }
        except Exception as exc:
            return {
                "error": f"Service unavailable: {exc}",
                "service_url": url,
            }

    async def elevated_search(
        self,
        query: str,
        mode: str = "auto",
        source_mode: str = "web",
        depth: str = "balanced",
        __event_emitter__: Optional[Any] = None,
        __user__: Optional[dict] = None,
    ) -> str:
        user_valves = self._resolve_user_valves(__user__)
        selected_mode = mode or self._get_user_valve(user_valves, "mode", "auto")
        include_citations = self._get_user_valve(user_valves, "include_citations", True)
        max_iterations = self._get_user_valve(user_valves, "max_iterations", 4)
        show_status = self._get_user_valve(user_valves, "show_status_updates", True)

        if show_status:
            await self._emit_status(__event_emitter__, f"Calling research backend: mode={selected_mode}")

        payload = {
            "query": query,
            "mode": selected_mode,
            "source_mode": source_mode,
            "depth": depth,
            "max_iterations": max_iterations,
            "include_citations": include_citations,
            "include_debug": False,
            "include_legacy": False,
            "strict_runtime": False,
            "user_context": {},
        }

        response = self._post_json("/internal/search", payload)

        if show_status:
            await self._emit_status(__event_emitter__, "Research backend request complete", done=True)

        return json.dumps(response, ensure_ascii=False)

    async def fetch_page(
        self,
        url: str,
        __event_emitter__: Optional[Any] = None,
        __user__: Optional[dict] = None,
    ) -> str:
        if __user__:
            _ = __user__
        await self._emit_status(__event_emitter__, f"Fetching via backend: {url}")
        response = self._post_json("/fetch", {"url": url})
        await self._emit_status(__event_emitter__, "Fetch complete", done=True)
        return json.dumps(response, ensure_ascii=False)

    async def extract_page_structure(
        self,
        url: str,
        components: str = "all",
        __event_emitter__: Optional[Any] = None,
        __user__: Optional[dict] = None,
    ) -> str:
        if __user__:
            _ = __user__
        await self._emit_status(__event_emitter__, f"Extracting via backend: {url}")
        response = self._post_json("/extract", {"url": url, "components": components})
        await self._emit_status(__event_emitter__, "Extraction complete", done=True)
        return json.dumps(response, ensure_ascii=False)

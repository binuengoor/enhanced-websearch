from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List

import httpx


logger = logging.getLogger(__name__)


class ResultCompiler:
    def __init__(self, enabled: bool, base_url: str, timeout_s: int, model_id: str):
        self.enabled = enabled
        self.base_url = (base_url or "").rstrip("/")
        self.timeout_s = timeout_s
        self.model_id = model_id.strip()

    @property
    def active(self) -> bool:
        return bool(self.enabled and self.base_url and self.model_id)

    async def vet_research_response(
        self,
        query: str,
        response: Dict[str, Any],
        fallback_query: str | None = None,
    ) -> Dict[str, Any] | None:
        if not self.active:
            return None

        diagnostics = response.get("diagnostics", {}) if isinstance(response, dict) else {}
        findings = response.get("findings", []) if isinstance(response, dict) else []
        citations = response.get("citations", []) if isinstance(response, dict) else []
        sources = response.get("sources", []) if isinstance(response, dict) else []

        prompt = json.dumps(
            {
                "task": "Assess whether a long-form research response is useful enough to return.",
                "query": query,
                "response": {
                    "direct_answer": response.get("direct_answer", "") if isinstance(response, dict) else "",
                    "summary": response.get("summary", "") if isinstance(response, dict) else "",
                    "body": response.get("body", response.get("direct_answer", "")) if isinstance(response, dict) else "",
                    "findings_count": len(findings),
                    "citations_count": len(citations),
                    "sources_count": len(sources),
                    "confidence": response.get("confidence") if isinstance(response, dict) else None,
                    "warnings": diagnostics.get("warnings", []) if isinstance(diagnostics, dict) else [],
                    "errors": diagnostics.get("errors", []) if isinstance(diagnostics, dict) else [],
                    "synthesis": diagnostics.get("synthesis", {}) if isinstance(diagnostics, dict) else {},
                },
                "fallback_query_hint": fallback_query,
                "rules": [
                    "Return JSON only.",
                    "useful must be true only if the answer is grounded, non-empty, and not generic.",
                    "A preserved longform body is desirable when it contains substantive grounded content; reject only if the body is empty, filler, or unsupported.",
                    "If not useful, provide a short fallback_query for a fresh concise search.",
                    "Prefer a fallback query that narrows the query while preserving user intent.",
                ],
                "output_schema": {
                    "useful": "boolean",
                    "reason": "string",
                    "fallback_query": "string|null",
                },
            },
            ensure_ascii=True,
        )

        payload = {
            "model": self.model_id,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a strict final quality gate for long-form web research. "
                        "You must only approve responses that are grounded, useful, and non-generic. "
                        "Do not penalize a response merely for being long if the body is substantive and grounded. "
                        "Return JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "max_tokens": 180,
            "response_format": {"type": "json_object"},
        }

        headers = {"Content-Type": "application/json"}
        token = os.getenv("EWS_COMPILER_API_KEY", "") or os.getenv("LITELLM_API_KEY", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        endpoint = self._chat_endpoint()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.post(endpoint, json=payload, headers=headers)
            if resp.status_code >= 400:
                body_preview = resp.text[:400].replace("\n", " ") if resp.text else ""
                logger.warning(
                    "event=research_vet_http_error status=%s model=%s endpoint=%s body=%r",
                    resp.status_code,
                    self.model_id,
                    endpoint,
                    body_preview,
                )
                return None

            body = resp.json()
            content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
            if isinstance(content, list):
                content = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            parsed = self._parse_compiler_content(content)
            if not parsed:
                return None

            useful = parsed.get("useful")
            if isinstance(useful, str):
                useful = useful.strip().lower() in {"1", "true", "yes", "on"}
            if not isinstance(useful, bool):
                return None

            reason = parsed.get("reason")
            fallback = parsed.get("fallback_query")
            return {
                "useful": useful,
                "reason": str(reason).strip() if isinstance(reason, str) else "",
                "fallback_query": str(fallback).strip() if isinstance(fallback, str) and fallback.strip() else None,
            }
        except Exception as exc:
            logger.warning(
                "event=research_vet_error model=%s endpoint=%s error_type=%s error=%r",
                self.model_id,
                endpoint,
                type(exc).__name__,
                exc,
            )
            return None

    async def summarize_vane_content(
        self,
        query: str,
        body: str,
        vane_summary: str | None = None,
    ) -> Dict[str, str] | None:
        if not self.active:
            return None

        prompt = json.dumps(
            {
                "task": "Shape an accepted long-form research answer into a direct answer and a short summary.",
                "query": query,
                "body": body,
                "vane_summary": vane_summary or "",
                "output_schema": {
                    "direct_answer": "string",
                    "summary": "string",
                    "direct_source": "vane_summary|llm_summary",
                    "summary_source": "vane_summary|llm_summary",
                },
                "rules": [
                    "Return JSON only.",
                    "Preserve the user's intent and the factual meaning of the body.",
                    "direct_answer must be a genuinely direct answer, not a verbatim prefix clipped from the body.",
                    "summary must be shorter than direct_answer and read like a concise synthesis, not a substring truncation.",
                    "Reuse vane_summary when it is already strong and faithful; otherwise rewrite from the body.",
                    "Do not invent facts, numbers, dates, entities, or citations.",
                ],
            },
            ensure_ascii=True,
        )

        payload = {
            "model": self.model_id,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You rewrite grounded research answers into shorter forms. "
                        "Only use the provided body and optional summary. "
                        "Return JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "max_tokens": 320,
            "response_format": {"type": "json_object"},
        }

        headers = {"Content-Type": "application/json"}
        token = os.getenv("EWS_COMPILER_API_KEY", "") or os.getenv("LITELLM_API_KEY", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        endpoint = self._chat_endpoint()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.post(endpoint, json=payload, headers=headers)
            if resp.status_code >= 400:
                logger.warning(
                    "event=vane_summary_http_error status=%s model=%s endpoint=%s",
                    resp.status_code,
                    self.model_id,
                    endpoint,
                )
                return None

            body_json = resp.json()
            content = body_json.get("choices", [{}])[0].get("message", {}).get("content", "")
            if isinstance(content, list):
                content = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )

            parsed = self._parse_compiler_content(content)
            if not isinstance(parsed, dict):
                return None

            direct_answer = parsed.get("direct_answer")
            summary = parsed.get("summary")
            direct_source = parsed.get("direct_source")
            summary_source = parsed.get("summary_source")
            if not isinstance(direct_answer, str) or not direct_answer.strip():
                return None
            if not isinstance(summary, str) or not summary.strip():
                return None

            direct_source = direct_source.strip() if isinstance(direct_source, str) else "llm_summary"
            summary_source = summary_source.strip() if isinstance(summary_source, str) else "llm_summary"
            if direct_source not in {"vane_summary", "llm_summary"}:
                direct_source = "llm_summary"
            if summary_source not in {"vane_summary", "llm_summary"}:
                summary_source = "llm_summary"

            return {
                "direct_answer": direct_answer.strip(),
                "summary": summary.strip(),
                "direct_source": direct_source,
                "summary_source": summary_source,
            }
        except Exception as exc:
            logger.warning(
                "event=vane_summary_error model=%s endpoint=%s error_type=%s error=%r",
                self.model_id,
                endpoint,
                type(exc).__name__,
                exc,
            )
            return None

    def _chat_endpoint(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        if self.base_url.endswith("/v1"):
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/v1/chat/completions"

    def _parse_compiler_content(self, content: Any) -> Dict[str, Any]:
        if isinstance(content, dict):
            if isinstance(content.get("results"), list):
                return content
            if content.get("depth") is not None and content.get("max_iterations") is not None:
                return content
            return {}

        if isinstance(content, list):
            return {"results": content}

        if not isinstance(content, str):
            return {}

        text = content.strip()
        if not text:
            return {}

        # Try direct JSON first.
        parsed = self._try_parse_json(text)
        if parsed:
            return parsed

        # Try fenced JSON blocks.
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL | re.IGNORECASE)
        if fence_match:
            parsed = self._try_parse_json(fence_match.group(1))
            if parsed:
                return parsed

        # Last attempt: extract outermost object/array slice.
        start_obj, end_obj = text.find("{"), text.rfind("}")
        if start_obj != -1 and end_obj > start_obj:
            parsed = self._try_parse_json(text[start_obj : end_obj + 1])
            if parsed:
                return parsed

        start_arr, end_arr = text.find("["), text.rfind("]")
        if start_arr != -1 and end_arr > start_arr:
            parsed = self._try_parse_json(text[start_arr : end_arr + 1])
            if parsed:
                return parsed

        logger.warning("event=compiler_parse_error preview=%r", text[:220])
        return {}

    def _try_parse_json(self, text: str) -> Dict[str, Any]:
        try:
            obj = json.loads(text)
        except Exception:
            return {}

        if isinstance(obj, dict):
            if isinstance(obj.get("results"), list):
                return obj
            return {}
        if isinstance(obj, list):
            return {"results": obj}
        return {}



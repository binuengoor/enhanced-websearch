from __future__ import annotations

import re
from html import unescape
from io import BytesIO
from typing import Any, Dict

import httpx
from bs4 import BeautifulSoup


class PageFetcher:
    CAPTCHA_MARKERS = [
        "captcha",
        "just a moment",
        "checking your browser",
        "security check",
        "access denied",
    ]

    def __init__(self, timeout_s: int, max_chars: int, flaresolverr_url: str, user_agent: str):
        self.timeout_s = timeout_s
        self.max_chars = max_chars
        self.flaresolverr_url = flaresolverr_url
        self.headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/pdf,application/xhtml+xml",
        }

    async def fetch(self, url: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout_s, follow_redirects=True, headers=self.headers) as client:
            resp = await client.get(url)

        content_type = (resp.headers.get("content-type") or "").lower()
        if "application/pdf" in content_type or url.lower().endswith(".pdf"):
            text = self._extract_pdf(resp.content)
            return {
                "url": str(resp.url),
                "title": url.split("/")[-1],
                "content": text,
                "source": "pdf",
                "error": None,
            }

        html = resp.text
        if self._looks_blocked(resp.status_code, html):
            fallback = await self._flaresolverr(url)
            if fallback:
                html = fallback

        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else str(resp.url)
        for node in soup(["script", "style", "noscript", "nav", "footer", "header", "aside"]):
            node.decompose()
        content = "\n".join([line.strip() for line in soup.get_text("\n").splitlines() if line.strip()])
        return {
            "url": str(resp.url),
            "title": title,
            "content": content[: self.max_chars],
            "source": "html",
            "error": None,
        }

    async def extract(self, url: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout_s, follow_redirects=True, headers=self.headers) as client:
            resp = await client.get(url)

        soup = BeautifulSoup(resp.text, "html.parser")
        out = {
            "url": str(resp.url),
            "title": soup.title.get_text(strip=True) if soup.title else "",
            "meta": {},
            "headings": [],
            "links": [],
            "sections": [],
            "tables": [],
            "code_blocks": [],
            "lists": [],
            "source": "html",
            "error": None,
        }
        desc = soup.find("meta", attrs={"name": "description"})
        if desc and desc.get("content"):
            out["meta"]["description"] = desc["content"]

        for h in soup.find_all(re.compile(r"^h[1-6]$")):
            text = h.get_text(strip=True)
            if text:
                out["headings"].append({"level": int(h.name[1]), "text": text, "id": h.get("id", "")})

        seen = set()
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            if href in seen:
                continue
            seen.add(href)
            out["links"].append({"url": href, "text": a.get_text(strip=True) or "[no text]"})
            if len(out["links"]) >= 200:
                break

        return out

    def _looks_blocked(self, status_code: int, html: str) -> bool:
        if status_code in {403, 429, 503}:
            return True
        lower = html.lower()[:5000]
        return sum(1 for marker in self.CAPTCHA_MARKERS if marker in lower) >= 2

    async def _flaresolverr(self, url: str) -> str:
        if not self.flaresolverr_url:
            return ""
        payload = {"cmd": "request.get", "url": url, "maxTimeout": self.timeout_s * 1000}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s + 10) as client:
                resp = await client.post(self.flaresolverr_url, json=payload)
            if resp.status_code >= 400:
                return ""
            body = resp.json()
            if body.get("status") == "ok":
                return body.get("solution", {}).get("response", "")
        except Exception:
            return ""
        return ""

    def _extract_pdf(self, content: bytes) -> str:
        try:
            import pypdf

            reader = pypdf.PdfReader(BytesIO(content))
            return "\n\n".join([page.extract_text() or "" for page in reader.pages])[: self.max_chars]
        except Exception:
            pass

        try:
            import PyPDF2

            reader = PyPDF2.PdfReader(BytesIO(content))
            return "\n\n".join([page.extract_text() or "" for page in reader.pages])[: self.max_chars]
        except Exception:
            return "[PDF detected but extraction backend unavailable]"

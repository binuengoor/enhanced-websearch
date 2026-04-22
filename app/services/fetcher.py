from __future__ import annotations

import logging
import re
from html import unescape
from io import BytesIO
from typing import Any, Dict

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


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
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s, follow_redirects=True, headers=self.headers) as client:
                resp = await client.get(url)
        except httpx.HTTPError as exc:
            logger.warning("fetch failed for %s: %s", url, exc)
            return {
                "url": url,
                "title": url,
                "content": "",
                "source": "html",
                "language": "",
                "published_at": "",
                "last_updated": "",
                "error": f"fetch_failed:{type(exc).__name__}",
            }

        if resp.status_code >= 400:
            logger.warning("fetch returned HTTP %s for %s", resp.status_code, resp.url)
            return {
                "url": str(resp.url),
                "title": str(resp.url),
                "content": "",
                "source": "html",
                "language": "",
                "published_at": "",
                "last_updated": str(resp.headers.get("last-modified") or "").strip(),
                "error": f"http_status:{resp.status_code}",
            }

        content_type = (resp.headers.get("content-type") or "").lower()
        if "application/pdf" in content_type or url.lower().endswith(".pdf"):
            text = self._extract_pdf(resp.content)
            return {
                "url": str(resp.url),
                "title": url.split("/")[-1],
                "content": text,
                "source": "pdf",
                "language": "",
                "published_at": "",
                "last_updated": "",
                "error": None,
            }

        html = resp.text
        if self._looks_blocked(resp.status_code, html):
            fallback = await self._flaresolverr(url)
            if fallback:
                html = fallback

        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else str(resp.url)
        language = self._detect_language(soup)
        published_at, last_updated = self._extract_dates(soup, resp.headers)
        for node in soup(["script", "style", "noscript", "nav", "footer", "header", "aside"]):
            node.decompose()
        content = "\n".join([line.strip() for line in soup.get_text("\n").splitlines() if line.strip()])
        return {
            "url": str(resp.url),
            "title": title,
            "content": content[: self.max_chars],
            "source": "html",
            "language": language,
            "published_at": published_at,
            "last_updated": last_updated,
            "error": None,
        }

    async def extract(self, url: str) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s, follow_redirects=True, headers=self.headers) as client:
                resp = await client.get(url)
        except httpx.HTTPError as exc:
            logger.warning("extract failed for %s: %s", url, exc)
            return {
                "url": url,
                "title": "",
                "meta": {},
                "headings": [],
                "links": [],
                "sections": [],
                "tables": [],
                "code_blocks": [],
                "lists": [],
                "source": "html",
                "error": f"extract_failed:{type(exc).__name__}",
            }

        if resp.status_code >= 400:
            logger.warning("extract returned HTTP %s for %s", resp.status_code, resp.url)
            return {
                "url": str(resp.url),
                "title": "",
                "meta": {},
                "headings": [],
                "links": [],
                "sections": [],
                "tables": [],
                "code_blocks": [],
                "lists": [],
                "source": "html",
                "error": f"http_status:{resp.status_code}",
            }

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

    def _detect_language(self, soup: BeautifulSoup) -> str:
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            return html_tag.get("lang", "").split("-")[0].lower().strip()

        meta_lang = soup.find("meta", attrs={"http-equiv": re.compile("content-language", re.I)})
        if meta_lang and meta_lang.get("content"):
            return str(meta_lang.get("content", "")).split(",")[0].split("-")[0].lower().strip()
        return ""

    def _extract_dates(self, soup: BeautifulSoup, headers: httpx.Headers) -> tuple[str, str]:
        published_at = ""
        last_updated = ""

        publish_keys = [
            ("property", "article:published_time"),
            ("name", "pubdate"),
            ("name", "publish_date"),
            ("name", "date"),
        ]
        update_keys = [
            ("property", "article:modified_time"),
            ("name", "lastmod"),
            ("name", "last-modified"),
            ("name", "updated_time"),
        ]

        for key, value in publish_keys:
            node = soup.find("meta", attrs={key: value})
            if node and node.get("content"):
                published_at = str(node.get("content", "")).strip()
                break

        for key, value in update_keys:
            node = soup.find("meta", attrs={key: value})
            if node and node.get("content"):
                last_updated = str(node.get("content", "")).strip()
                break

        if not last_updated:
            last_updated = str(headers.get("last-modified") or "").strip()

        return published_at, last_updated

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
                logger.warning("flaresolverr returned HTTP %s for %s", resp.status_code, url)
                return ""
            body = resp.json()
            if body.get("status") == "ok":
                return body.get("solution", {}).get("response", "")
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("flaresolverr fallback failed for %s: %s", url, exc)
            return ""
        return ""

    def _extract_pdf(self, content: bytes) -> str:
        try:
            import pypdf

            reader = pypdf.PdfReader(BytesIO(content))
            return "\n\n".join([page.extract_text() or "" for page in reader.pages])[: self.max_chars]
        except (ImportError, ModuleNotFoundError, AttributeError, TypeError, ValueError) as exc:
            logger.warning("pypdf extraction failed: %s", exc)

        try:
            import PyPDF2

            reader = PyPDF2.PdfReader(BytesIO(content))
            return "\n\n".join([page.extract_text() or "" for page in reader.pages])[: self.max_chars]
        except (ImportError, ModuleNotFoundError, AttributeError, TypeError, ValueError) as exc:
            logger.warning("PyPDF2 extraction failed: %s", exc)
            return "[PDF detected but extraction backend unavailable]"

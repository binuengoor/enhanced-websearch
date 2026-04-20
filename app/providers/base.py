from __future__ import annotations

from typing import Any, Dict, List


class ProviderError(Exception):
    pass


class RateLimitError(ProviderError):
    pass


class SearchProvider:
    name: str

    async def search(self, query: str, options: Dict[str, Any]) -> List[Dict[str, Any]]:
        raise NotImplementedError

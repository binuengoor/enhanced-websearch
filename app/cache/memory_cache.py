from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, Optional


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class InMemoryCache:
    def __init__(self, max_entries: int = 1000):
        self.max_entries = max_entries
        self._store: Dict[str, CacheEntry] = {}
        self._lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            if entry.expires_at <= time.time():
                self._store.pop(key, None)
                return None
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        with self._lock:
            if len(self._store) >= self.max_entries:
                oldest = min(self._store.items(), key=lambda item: item[1].expires_at)[0]
                self._store.pop(oldest, None)
            self._store[key] = CacheEntry(value=value, expires_at=time.time() + ttl_seconds)

    def stats(self) -> Dict[str, Any]:
        now = time.time()
        with self._lock:
            alive = sum(1 for v in self._store.values() if v.expires_at > now)
            return {
                "entries": alive,
                "max_entries": self.max_entries,
            }

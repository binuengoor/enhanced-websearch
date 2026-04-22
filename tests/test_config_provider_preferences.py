from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from app.core.config import load_config


class ProviderPreferencesConfigTests(unittest.TestCase):
    def _write_config(self, content: str) -> str:
        handle = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
        handle.write(textwrap.dedent(content))
        handle.flush()
        handle.close()
        self.addCleanup(lambda: Path(handle.name).unlink(missing_ok=True))
        return handle.name

    def test_load_config_accepts_known_provider_preferences(self):
        path = self._write_config(
            """
            modes:
              fast:
                max_provider_attempts: 1
                max_queries: 1
                max_pages_to_fetch: 1
            providers:
              - name: searxng
                kind: searxng
            provider_preferences:
              fast:
                prefer: [searxng]
            """
        )

        config = load_config(path)

        self.assertEqual(config.provider_preferences["fast"].prefer, ["searxng"])

    def test_load_config_rejects_unknown_provider_preferences(self):
        path = self._write_config(
            """
            modes:
              fast:
                max_provider_attempts: 1
                max_queries: 1
                max_pages_to_fetch: 1
            providers:
              - name: searxng
                kind: searxng
            provider_preferences:
              research:
                prefer: [exa]
                avoid: [ghost]
            """
        )

        with self.assertRaisesRegex(ValueError, "unknown providers: exa, ghost"):
            load_config(path)


if __name__ == "__main__":
    unittest.main()

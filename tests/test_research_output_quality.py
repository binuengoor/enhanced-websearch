from __future__ import annotations

import unittest


class ResearchOutputQualityTests(unittest.TestCase):
    def test_local_research_quality_suite_removed_in_vane_proxy_milestone(self):
        self.skipTest("Obsolete after /research became a transparent Vane proxy")


if __name__ == "__main__":
    unittest.main()

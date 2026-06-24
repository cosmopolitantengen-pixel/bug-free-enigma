import os
import sys
import unittest


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import scripts.release_gate as release_gate


class ReleaseGateTests(unittest.TestCase):
    def test_release_gate_passes_current_contract(self):
        self.assertEqual(release_gate.main(), 0)

    def test_required_api_paths_cover_recent_production_surfaces(self):
        self.assertIn("/deployment/readiness", release_gate.REQUIRED_API_PATHS)
        self.assertIn("/github/absorptions/import", release_gate.REQUIRED_API_PATHS)
        self.assertIn("/runbooks", release_gate.REQUIRED_API_PATHS)


if __name__ == "__main__":
    unittest.main()

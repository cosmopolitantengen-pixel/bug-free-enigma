import json
import os
import unittest


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class NextDashboardTests(unittest.TestCase):
    def test_next_console_has_required_operational_surfaces(self):
        console_path = os.path.join(ROOT_DIR, "apps", "web", "components", "operations-console.tsx")
        styles_path = os.path.join(ROOT_DIR, "apps", "web", "app", "globals.css")
        with open(console_path, "r", encoding="utf-8") as handle:
            console = handle.read()
        with open(styles_path, "r", encoding="utf-8") as handle:
            styles = handle.read()

        for label in ["Overview", "Work queue", "Scheduler", "Catalog", "Governance", "System"]:
            self.assertIn(label, console)
        for endpoint in [
            "/dashboard/summary", "/system/integrity", "/deployment/readiness", "/workflows/run", "/approvals",
            "/incidents", "/schedules", "/scheduler/executions", "/audit-logs",
            "/database/schema", "/scheduler/queue-health",
            "/models/providers", "/knowledge/embeddings/status", "/alerts/status", "/runbooks",
        ]:
            self.assertIn(endpoint, console)
        self.assertIn("Loading operations data", console)
        self.assertIn("No tasks", console)
        self.assertIn("@media (max-width: 760px)", styles)

    def test_frontend_dependencies_are_pinned(self):
        package_path = os.path.join(ROOT_DIR, "apps", "web", "package.json")
        with open(package_path, "r", encoding="utf-8") as handle:
            package = json.load(handle)

        self.assertEqual(package["dependencies"]["next"], "16.2.9")
        self.assertEqual(package["dependencies"]["react"], "19.2.7")
        self.assertIn("typecheck", package["scripts"])
        self.assertEqual(package["scripts"]["e2e"], "node scripts/run-e2e.mjs")
        self.assertIn("@playwright/test", package["devDependencies"])

    def test_frontend_is_wired_into_production_packaging_and_ci(self):
        paths = {
            "dockerfile": os.path.join(ROOT_DIR, "apps", "web", "Dockerfile"),
            "compose": os.path.join(ROOT_DIR, "docker-compose.yml"),
            "workflow": os.path.join(ROOT_DIR, ".github", "workflows", "backend.yml"),
            "playwright": os.path.join(ROOT_DIR, "apps", "web", "playwright.config.ts"),
            "e2e": os.path.join(ROOT_DIR, "apps", "web", "e2e", "operations-console.spec.ts"),
            "e2e_runner": os.path.join(ROOT_DIR, "apps", "web", "scripts", "run-e2e.mjs"),
        }
        contents = {}
        for name, path in paths.items():
            with open(path, "r", encoding="utf-8") as handle:
                contents[name] = handle.read()

        self.assertIn("/app/.next/standalone", contents["dockerfile"])
        self.assertIn("NEXT_PUBLIC_API_BASE", contents["dockerfile"])
        self.assertIn("  web:", contents["compose"])
        self.assertIn("context: apps/web", contents["compose"])
        self.assertIn("npm run typecheck", contents["workflow"])
        self.assertIn("npm run build", contents["workflow"])
        self.assertIn("npx playwright install --with-deps chromium", contents["workflow"])
        self.assertIn("npm run e2e", contents["workflow"])
        self.assertIn("desktop-chromium", contents["playwright"])
        self.assertIn("mobile-chromium", contents["playwright"])
        self.assertIn("Workflow accepted:", contents["e2e"])
        self.assertIn("taskkill", contents["e2e_runner"])
        self.assertIn("@playwright/test/cli.js", contents["e2e_runner"])


if __name__ == "__main__":
    unittest.main()

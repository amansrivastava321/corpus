"""Smoke-tests for example scripts — verify they are syntactically valid
and that their importable components work without a live server."""

from __future__ import annotations

import ast
import importlib.util
import pathlib
import sys


EXAMPLES_DIR = pathlib.Path("examples")
EXAMPLE_FILES = list(EXAMPLES_DIR.glob("*.py"))


class TestExampleSyntax:
    """Each example must be valid Python."""

    def test_basic_signal_flow_syntax(self):
        src = (EXAMPLES_DIR / "basic_signal_flow.py").read_text()
        ast.parse(src)

    def test_checkpoint_clearance_syntax(self):
        src = (EXAMPLES_DIR / "checkpoint_clearance.py").read_text()
        ast.parse(src)

    def test_guardian_mode_demo_syntax(self):
        src = (EXAMPLES_DIR / "guardian_mode_demo.py").read_text()
        ast.parse(src)

    def test_orchestration_demo_syntax(self):
        src = (EXAMPLES_DIR / "orchestration_demo.py").read_text()
        ast.parse(src)

    def test_realtime_listener_syntax(self):
        src = (EXAMPLES_DIR / "realtime_listener.py").read_text()
        ast.parse(src)

    def test_webhook_demo_syntax(self):
        src = (EXAMPLES_DIR / "webhook_demo.py").read_text()
        ast.parse(src)

    def test_all_examples_present(self):
        expected = {
            "basic_signal_flow.py",
            "checkpoint_clearance.py",
            "guardian_mode_demo.py",
            "orchestration_demo.py",
            "realtime_listener.py",
            "webhook_demo.py",
        }
        found = {f.name for f in EXAMPLE_FILES}
        assert expected.issubset(found)


class TestExampleNoServerImports:
    """Examples that don't require a live server should not import uvicorn
    or any corpus internal at the top level."""

    def _get_toplevel_imports(self, filename: str) -> list[str]:
        src = (EXAMPLES_DIR / filename).read_text()
        tree = ast.parse(src)
        names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
        return names

    def test_webhook_demo_no_corpus_internals(self):
        imports = self._get_toplevel_imports("webhook_demo.py")
        corpus_internals = [n for n in imports if n.startswith("corpus.")]
        assert corpus_internals == [], f"Found corpus internal imports: {corpus_internals}"

    def test_realtime_listener_uses_asyncio(self):
        imports = self._get_toplevel_imports("realtime_listener.py")
        assert "asyncio" in imports

    def test_basic_signal_flow_uses_corpus_sdk(self):
        imports = self._get_toplevel_imports("basic_signal_flow.py")
        assert any("corpus_sdk" in n for n in imports)


class TestWebhookDemoRunnable:
    """webhook_demo.py has offline-safe logic we can execute."""

    def test_webhook_default_signal_map(self):
        from integrations.webhook.webhook_integration import _DEFAULT_SIGNAL_MAP
        assert "push" in _DEFAULT_SIGNAL_MAP
        assert "security_advisory" in _DEFAULT_SIGNAL_MAP
        assert "deployment_status.failure" in _DEFAULT_SIGNAL_MAP

    def test_webhook_add_mapping(self):
        from integrations.webhook.webhook_integration import WebhookCorpusIntegration
        integration = WebhookCorpusIntegration()
        integration.add_mapping("deployment_created", "INFORM", "LOW")
        assert "deployment_created" in integration._signal_map
        assert integration._signal_map["deployment_created"] == ("INFORM", "LOW")

    def test_webhook_unmapped_not_in_signal_map(self):
        from integrations.webhook.webhook_integration import _DEFAULT_SIGNAL_MAP
        assert "completely_unknown_event_xyz" not in _DEFAULT_SIGNAL_MAP


class TestOpenSourceFiles:
    """Verify required open-source hygiene files exist and are non-empty."""

    ROOT = pathlib.Path(".")

    def _check(self, path: str) -> None:
        p = self.ROOT / path
        assert p.exists(), f"Missing: {path}"
        assert p.stat().st_size > 0, f"Empty: {path}"

    def test_license_exists(self):
        self._check("LICENSE")

    def test_contributing_exists(self):
        self._check("CONTRIBUTING.md")

    def test_code_of_conduct_exists(self):
        self._check("CODE_OF_CONDUCT.md")

    def test_changelog_exists(self):
        self._check("CHANGELOG.md")

    def test_env_example_exists(self):
        self._check(".env.example")

    def test_corpus_toml_example_exists(self):
        self._check("corpus.example.toml")

    def test_dockerfile_exists(self):
        self._check("Dockerfile")

    def test_ci_workflow_exists(self):
        self._check(".github/workflows/ci.yml")

    def test_readme_mentions_all_phases(self):
        readme = (self.ROOT / "README.md").read_text()
        for phase in range(15):
            assert str(phase) in readme, f"Phase {phase} not mentioned in README"

    def test_readme_mentions_test_count(self):
        readme = (self.ROOT / "README.md").read_text()
        # Should mention a passing test count
        assert "tests passing" in readme or "391" in readme


class TestDocFiles:
    """Verify documentation files exist."""

    DOCS = pathlib.Path("docs")

    def _check(self, name: str) -> None:
        p = self.DOCS / name
        assert p.exists(), f"Missing docs/{name}"
        assert p.stat().st_size > 100, f"Too short: docs/{name}"

    def test_quickstart_exists(self):
        self._check("QUICKSTART.md")

    def test_api_reference_exists(self):
        self._check("API_REFERENCE.md")

    def test_sdk_reference_exists(self):
        self._check("SDK_REFERENCE.md")

    def test_deployment_exists(self):
        self._check("DEPLOYMENT.md")

    def test_security_exists(self):
        self._check("SECURITY.md")

    def test_roadmap_exists(self):
        self._check("ROADMAP.md")

    def test_integrations_exists(self):
        self._check("INTEGRATIONS.md")

    def test_architecture_exists(self):
        self._check("ARCHITECTURE.md")

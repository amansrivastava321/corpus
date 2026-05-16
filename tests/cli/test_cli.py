"""Phase 14 — CLI tests."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from corpus.server import create_app


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def live_client():
    with TestClient(create_app(db_path=":memory:")) as c:
        yield c


class TestCLIStructure:
    def test_cli_imports(self):
        from corpus.cli.main import cli
        assert cli is not None

    def test_all_commands_registered(self):
        from corpus.cli.main import cli
        commands = set(cli.commands.keys())
        expected = {"serve", "doctor", "products", "signals", "checkpoints",
                    "policy", "guardian", "dashboard", "export", "import"}
        assert expected.issubset(commands)

    def test_entrypoint_callable(self):
        from corpus.runtime.cli import main
        assert callable(main)

    def test_products_group_has_list(self):
        from corpus.cli.main import cli
        assert "list" in cli.commands["products"].commands  # type: ignore[attr-defined]

    def test_signals_group_has_emit_pending(self):
        from corpus.cli.main import cli
        sigs = cli.commands["signals"].commands  # type: ignore[attr-defined]
        assert "emit" in sigs
        assert "pending" in sigs

    def test_checkpoints_group_has_list(self):
        from corpus.cli.main import cli
        assert "list" in cli.commands["checkpoints"].commands  # type: ignore[attr-defined]

    def test_policy_group_has_show(self):
        from corpus.cli.main import cli
        assert "show" in cli.commands["policy"].commands  # type: ignore[attr-defined]

    def test_guardian_group_has_status(self):
        from corpus.cli.main import cli
        assert "status" in cli.commands["guardian"].commands  # type: ignore[attr-defined]

    def test_dashboard_group_has_summary(self):
        from corpus.cli.main import cli
        assert "summary" in cli.commands["dashboard"].commands  # type: ignore[attr-defined]


class TestCLIHelp:
    def test_root_help(self, runner):
        from corpus.cli.main import cli
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "corpus" in result.output.lower()

    def test_serve_help(self, runner):
        from corpus.cli.main import cli
        result = runner.invoke(cli, ["serve", "--help"])
        assert result.exit_code == 0
        assert "--host" in result.output
        assert "--port" in result.output
        assert "--db" in result.output

    def test_signals_emit_help(self, runner):
        from corpus.cli.main import cli
        result = runner.invoke(cli, ["signals", "emit", "--help"])
        assert result.exit_code == 0
        assert "--source" in result.output
        assert "--target" in result.output
        assert "--type" in result.output
        assert "--message" in result.output

    def test_doctor_help(self, runner):
        from corpus.cli.main import cli
        result = runner.invoke(cli, ["doctor", "--help"])
        assert result.exit_code == 0

    def test_export_help(self, runner):
        from corpus.cli.main import cli
        result = runner.invoke(cli, ["export", "--help"])
        assert result.exit_code == 0
        assert "--output" in result.output

    def test_import_help(self, runner):
        from corpus.cli.main import cli
        result = runner.invoke(cli, ["import", "--help"])
        assert result.exit_code == 0


class TestCLIJsonFlag:
    def test_json_flag_on_doctor(self, runner, live_client):
        """doctor --json outputs valid JSON when server is reachable."""
        from corpus.cli.main import cli

        def _get_override(base_url, path):
            resp = live_client.get(path)
            resp.raise_for_status()
            return resp.json()

        import corpus.cli.main as m
        original = m._get
        m._get = _get_override
        try:
            result = runner.invoke(cli, ["--json", "doctor"])
            assert result.exit_code == 0
            parsed = json.loads(result.output)
            assert "status" in parsed
        finally:
            m._get = original

    def test_doctor_error_on_unreachable_server(self, runner):
        from corpus.cli.main import cli
        result = runner.invoke(cli, ["--url", "http://localhost:19999", "doctor"])
        assert result.exit_code != 0


class TestCLIProductsList:
    def test_products_list_json(self, runner, live_client):
        from corpus.cli.main import cli
        import corpus.cli.main as m

        def _get_override(base_url, path):
            resp = live_client.get(path)
            resp.raise_for_status()
            return resp.json()

        original = m._get
        m._get = _get_override
        try:
            result = runner.invoke(cli, ["--json", "products", "list"])
            assert result.exit_code == 0
            parsed = json.loads(result.output)
            assert "products" in parsed or isinstance(parsed, list)
        finally:
            m._get = original


class TestCLISignalsEmit:
    def test_signals_emit_invalid_payload_json(self, runner):
        from corpus.cli.main import cli
        result = runner.invoke(cli, [
            "signals", "emit",
            "--source", "A", "--target", "B",
            "--type", "INFORM", "--message", "hi",
            "--payload", "{not valid json}",
        ])
        assert result.exit_code != 0

    def test_signals_emit_valid(self, runner, live_client):
        from corpus.cli.main import cli
        import corpus.cli.main as m

        def _get_override(base_url, path):
            resp = live_client.get(path)
            resp.raise_for_status()
            return resp.json()

        def _post_override(base_url, path, body):
            resp = live_client.post(path, json=body)
            resp.raise_for_status()
            return resp.json()

        original_get = m._get
        original_post = m._post
        m._get = _get_override
        m._post = _post_override
        try:
            live_client.post("/products/register", json={
                "name": "A", "capabilities": [], "version": "1.0", "base_url": "http://a.local"
            })
            live_client.post("/products/register", json={
                "name": "B", "capabilities": [], "version": "1.0", "base_url": "http://b.local"
            })
            result = runner.invoke(cli, [
                "--json", "signals", "emit",
                "--source", "A", "--target", "B",
                "--type", "INFORM", "--message", "Hello from CLI",
            ])
            assert result.exit_code == 0
        finally:
            m._get = original_get
            m._post = original_post


class TestCLIExportImport:
    def test_export_creates_file(self, runner, live_client, tmp_path):
        from corpus.cli.main import cli
        import corpus.cli.main as m

        def _get_override(base_url, path):
            resp = live_client.get(path)
            resp.raise_for_status()
            return resp.json()

        original = m._get
        m._get = _get_override
        out = str(tmp_path / "export.json")
        try:
            result = runner.invoke(cli, ["export", "--output", out])
            assert result.exit_code == 0
            assert "Exported" in result.output
            with open(out) as f:
                data = json.load(f)
            assert "products" in data
        finally:
            m._get = original

    def test_import_from_export(self, runner, live_client, tmp_path):
        from corpus.cli.main import cli
        import corpus.cli.main as m

        # Create export file with one product
        export_file = tmp_path / "import_test.json"
        export_file.write_text(json.dumps({
            "products": {"products": [
                {"name": "ImportedProduct", "capabilities": ["test"]},
            ]},
        }))

        def _post_override(base_url, path, body):
            resp = live_client.post(path, json=body)
            resp.raise_for_status()
            return resp.json()

        original = m._post
        m._post = _post_override
        try:
            result = runner.invoke(cli, ["import", str(export_file)])
            assert result.exit_code == 0
            assert "Imported" in result.output
        finally:
            m._post = original

"""Phase 9 — Multi-Product Orchestration tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from corpus.orchestration.orchestration_models import (
    SynthesisDecision,
    TaskStatus,
    WorkflowStatus,
)
from corpus.orchestration.product_graph import ProductGraph
from corpus.orchestration.synthesis_engine import SynthesisEngine
from corpus.server import create_app


@pytest.fixture
def client():
    with TestClient(create_app(db_path=":memory:")) as c:
        yield c


def _register(client, name: str) -> dict:
    resp = client.post("/products/register", json={"name": name, "version": "1.0.0"})
    assert resp.status_code == 201
    return resp.json()


# ─── ProductGraph unit tests ─────────────────────────────────────────────────

class TestProductGraph:
    def test_upsert_and_find(self):
        g = ProductGraph()
        g.upsert("p1", "anvil", ["deploy", "audit"])
        g.upsert("p2", "inspectra", ["audit", "validate"])
        result = g.find_by_capability("audit")
        assert len(result) == 2

    def test_find_by_name(self):
        g = ProductGraph()
        g.upsert("p1", "Anvil", ["deploy"])
        node = g.find_by_name("anvil")
        assert node is not None
        assert node.product_id == "p1"

    def test_find_by_unknown_capability_empty(self):
        g = ProductGraph()
        g.upsert("p1", "anvil", ["deploy"])
        assert g.find_by_capability("nonexistent") == []

    def test_remove_product(self):
        g = ProductGraph()
        g.upsert("p1", "anvil", ["deploy"])
        g.remove("p1")
        assert g.find_by_capability("deploy") == []

    def test_all_capabilities(self):
        g = ProductGraph()
        g.upsert("p1", "anvil", ["deploy", "audit"])
        g.upsert("p2", "inspectra", ["validate"])
        caps = g.all_capabilities()
        assert "deploy" in caps
        assert "validate" in caps

    def test_to_dict_shape(self):
        g = ProductGraph()
        g.upsert("p1", "anvil", ["audit"])
        g.add_dependency("anvil", "inspectra", "monitors")
        d = g.to_dict()
        assert "nodes" in d
        assert "edges" in d
        assert d["edges"][0]["relationship"] == "monitors"


# ─── SynthesisEngine unit tests ──────────────────────────────────────────────

class TestSynthesisEngine:
    def _task(self, status: str, response: dict | None = None):
        from corpus.orchestration.orchestration_models import OrchestrationTask
        t = OrchestrationTask(
            target_product="inspectra",
            capability_required="audit",
        )
        t.status = TaskStatus(status)
        t.response = response
        return t

    def test_allow_when_no_issues(self):
        synth = SynthesisEngine()
        tasks = [self._task("RESPONDED", {"decision": "ALLOW"})]
        result = synth.synthesize(tasks, {})
        assert result.decision == SynthesisDecision.ALLOW

    def test_block_when_blocking_response(self):
        synth = SynthesisEngine()
        tasks = [self._task("RESPONDED", {"decision": "BLOCK"})]
        result = synth.synthesize(tasks, {})
        assert result.decision == SynthesisDecision.BLOCK

    def test_warn_when_timeout(self):
        synth = SynthesisEngine()
        tasks = [self._task("TIMEOUT")]
        result = synth.synthesize(tasks, {})
        assert result.decision == SynthesisDecision.WARN
        assert result.timeout_tasks == 1

    def test_policy_denied_always_blocks(self):
        synth = SynthesisEngine()
        tasks = [self._task("RESPONDED", {"decision": "ALLOW"})]
        result = synth.synthesize(tasks, {}, policy_authorized=False)
        assert result.decision == SynthesisDecision.BLOCK

    def test_gravity_block_contributes(self):
        synth = SynthesisEngine()
        tasks = []
        result = synth.synthesize(tasks, {}, gravity_action="BLOCK")
        assert result.decision == SynthesisDecision.BLOCK

    def test_gravity_reroute(self):
        synth = SynthesisEngine()
        result = SynthesisEngine().synthesize([], {}, gravity_action="REROUTE")
        assert result.decision == SynthesisDecision.REROUTE

    def test_memory_warnings(self):
        synth = SynthesisEngine()
        result = synth.synthesize([], {}, memory_block_count=5)
        # 5 historical blocks → warning
        assert result.decision in (SynthesisDecision.WARN, SynthesisDecision.ALLOW)

    def test_contributing_factors_list(self):
        synth = SynthesisEngine()
        tasks = [self._task("TIMEOUT")]
        result = synth.synthesize(tasks, {})
        assert len(result.contributing_factors) >= 1


# ─── REST API tests ───────────────────────────────────────────────────────────

class TestOrchestrationAPI:
    def _create_workflow(self, client, name="test-workflow", tasks=None) -> dict:
        payload = {
            "name": name,
            "initiating_product": "anvil",
            "subject": {"action": "refactor auth.py", "module": "auth"},
        }
        if tasks is not None:
            payload["tasks"] = tasks
        resp = client.post("/orchestration/workflows", json=payload)
        assert resp.status_code == 201, resp.text
        return resp.json()

    def test_create_workflow(self, client):
        wf = self._create_workflow(client)
        assert wf["name"] == "test-workflow"
        assert wf["status"] == "PENDING"
        assert "id" in wf

    def test_create_workflow_with_explicit_tasks(self, client):
        tasks = [
            {"target_product": "inspectra", "capability_required": "audit"}
        ]
        wf = self._create_workflow(client, tasks=tasks)
        assert len(wf["tasks"]) == 1
        assert wf["tasks"][0]["target_product"] == "inspectra"

    def test_get_workflow(self, client):
        wf = self._create_workflow(client)
        resp = client.get(f"/orchestration/workflows/{wf['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == wf["id"]

    def test_get_workflow_not_found(self, client):
        resp = client.get("/orchestration/workflows/nonexistent-id")
        assert resp.status_code == 404

    def test_start_workflow(self, client):
        wf = self._create_workflow(client)
        resp = client.post(f"/orchestration/workflows/{wf['id']}/start")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "COMPLETED"
        assert data["synthesis"] is not None
        assert "decision" in data["synthesis"]

    def test_start_workflow_returns_synthesis(self, client):
        tasks = [{"target_product": "inspectra", "capability_required": "audit"}]
        wf = self._create_workflow(client, tasks=tasks)
        resp = client.post(f"/orchestration/workflows/{wf['id']}/start")
        data = resp.json()
        synth = data["synthesis"]
        assert synth["decision"] in ("ALLOW", "WARN", "BLOCK", "REROUTE", "ESCALATE")
        assert 0.0 <= synth["confidence"] <= 1.0
        assert synth["reasoning"]

    def test_cancel_workflow(self, client):
        wf = self._create_workflow(client)
        resp = client.post(f"/orchestration/workflows/{wf['id']}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "CANCELLED"

    def test_cancel_already_completed_fails(self, client):
        wf = self._create_workflow(client)
        client.post(f"/orchestration/workflows/{wf['id']}/start")
        resp = client.post(f"/orchestration/workflows/{wf['id']}/cancel")
        assert resp.status_code == 400

    def test_start_completed_workflow_fails(self, client):
        wf = self._create_workflow(client)
        client.post(f"/orchestration/workflows/{wf['id']}/start")
        resp = client.post(f"/orchestration/workflows/{wf['id']}/start")
        assert resp.status_code == 400

    def test_list_workflows(self, client):
        self._create_workflow(client, "wf-a")
        self._create_workflow(client, "wf-b")
        resp = client.get("/orchestration/workflows")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 2

    def test_workflow_state_endpoint(self, client):
        wf = self._create_workflow(client)
        resp = client.get(f"/orchestration/workflows/{wf['id']}/state")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "task_count" in data

    def test_product_graph_endpoint(self, client):
        resp = client.get("/orchestration/products/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data

    def test_list_filter_by_product(self, client):
        self._create_workflow(client, "wf-x")
        resp = client.get("/orchestration/workflows", params={"product": "anvil"})
        assert resp.status_code == 200

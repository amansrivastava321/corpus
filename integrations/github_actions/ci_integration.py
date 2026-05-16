"""GitHub Actions / CI integration adapter."""

from __future__ import annotations


class CICorpusIntegration:
    """
    CI integration adapter.

    Capabilities: ci_status, test_history
    Emits workflow status signals and responds to CI status requests.
    """

    CAPABILITIES = ["ci_status", "test_history"]

    def __init__(self, corpus_url: str = "http://localhost:8000") -> None:
        from corpus_sdk import CorpusClient
        self._client = CorpusClient(
            product_name="CI",
            base_url=corpus_url,
        )
        self._connected = False

    def connect(self) -> None:
        self._client.connect()
        self._connected = True

    def report_ci_failure(self, repo: str, branch: str, run_url: str, target: str = "anvil") -> dict:
        if not self._connected:
            raise RuntimeError("Call connect() first")
        return self._client.block(
            target=target,
            message=f"CI failure on {repo}/{branch}",
            payload={
                "repo": repo,
                "branch": branch,
                "run_url": run_url,
                "capability": "ci_status",
                "status": "FAILED",
            },
        )

    def report_ci_success(self, repo: str, branch: str, target: str = "anvil") -> dict:
        if not self._connected:
            raise RuntimeError("Call connect() first")
        return self._client.inform(
            target=target,
            message=f"CI passed on {repo}/{branch}",
            payload={"repo": repo, "branch": branch, "status": "PASSED", "capability": "ci_status"},
        )

    def share_test_history(self, repo: str, history: list[dict]) -> dict:
        if not self._connected:
            raise RuntimeError("Call connect() first")
        return self._client.learn(
            target="*",
            message=f"Test history for {repo}",
            payload={"repo": repo, "history": history, "capability": "test_history"},
            broadcast=True,
        )

    def disconnect(self) -> None:
        if self._connected:
            self._client.disconnect()
            self._connected = False

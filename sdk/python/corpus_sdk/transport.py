"""
Transport abstraction for the Corpus SDK.

                 ┌─────────────────┐
CorpusClient ──► │  BaseTransport  │
                 └────────┬────────┘
                          │
              ┌───────────┼──────────────┐
              ▼           ▼              ▼
       HTTPTransport  InProcessTransport  (future: WsTransport, GrpcTransport)

HTTPTransport   — production; wraps httpx with retries + structured errors
InProcessTransport — testing; wraps a Starlette TestClient for zero-network tests
"""

import time
from typing import Any

import httpx

from corpus_sdk.exceptions import (
    CorpusAPIError,
    CorpusConnectionError,
    ProductAlreadyRegisteredError,
    ProductNotFoundError,
    SignalAcknowledgementError,
    SignalExpiredError,
    SignalNotFoundError,
    SignalRoutingError,
)

_ERROR_MAP = {
    409: ProductAlreadyRegisteredError,
    410: SignalExpiredError,
    422: None,  # resolved at runtime by error_code
}


def _raise_for(status_code: int, body: dict) -> None:
    message = body.get("message", "Unknown error")
    error_code = body.get("error", "unknown")

    if status_code == 404:
        cls = SignalNotFoundError if "signal" in message.lower() else ProductNotFoundError
        raise cls(status_code, message, error_code)
    if status_code == 409:
        raise ProductAlreadyRegisteredError(status_code, message, error_code)
    if status_code == 410:
        raise SignalExpiredError(status_code, message, error_code)
    if status_code == 422:
        if "ack" in error_code:
            raise SignalAcknowledgementError(status_code, message, error_code)
        raise SignalRoutingError(status_code, message, error_code)
    raise CorpusAPIError(status_code, message, error_code)


class BaseTransport:
    def get(self, path: str, **kwargs) -> Any:
        raise NotImplementedError

    def post(self, path: str, json: dict | None = None, **kwargs) -> Any:
        raise NotImplementedError

    def delete(self, path: str, **kwargs) -> Any:
        raise NotImplementedError


class HTTPTransport(BaseTransport):
    """Production HTTP transport with configurable retries and timeouts."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 10.0,
        retries: int = 3,
        retry_delay: float = 0.5,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._retries = retries
        self._retry_delay = retry_delay
        self._client = httpx.Client(base_url=self._base_url, timeout=timeout)

    def _request(self, method: str, path: str, **kwargs) -> Any:
        last_exc: Exception | None = None
        for attempt in range(self._retries):
            try:
                resp = self._client.request(method, path, **kwargs)
                if resp.status_code >= 400:
                    _raise_for(resp.status_code, resp.json())
                # 204 No Content
                if resp.status_code == 204:
                    return None
                return resp.json()
            except (CorpusAPIError,):
                raise  # don't retry API errors — they're deterministic
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < self._retries - 1:
                    time.sleep(self._retry_delay * (attempt + 1))
        raise CorpusConnectionError(
            f"Cannot reach Corpus at {self._base_url} after {self._retries} attempts: {last_exc}"
        )

    def get(self, path: str, **kwargs) -> Any:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, json: dict | None = None, **kwargs) -> Any:
        return self._request("POST", path, json=json, **kwargs)

    def delete(self, path: str, **kwargs) -> Any:
        return self._request("DELETE", path, **kwargs)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HTTPTransport":
        return self

    def __exit__(self, *_) -> None:
        self.close()


class InProcessTransport(BaseTransport):
    """
    Test transport that wraps a Starlette/FastAPI TestClient.

    Allows the SDK to be tested against a real in-memory Corpus server with no
    network involved. Inject via CorpusClient(transport=InProcessTransport(tc)).
    """

    def __init__(self, test_client: Any) -> None:
        self._client = test_client

    def _request(self, method: str, path: str, **kwargs) -> Any:
        resp = self._client.request(method, path, **kwargs)
        if resp.status_code >= 400:
            _raise_for(resp.status_code, resp.json())
        if resp.status_code == 204:
            return None
        return resp.json()

    def get(self, path: str, **kwargs) -> Any:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, json: dict | None = None, **kwargs) -> Any:
        return self._request("POST", path, json=json, **kwargs)

    def delete(self, path: str, **kwargs) -> Any:
        return self._request("DELETE", path, **kwargs)

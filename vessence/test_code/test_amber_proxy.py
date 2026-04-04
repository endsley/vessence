import asyncio

from vault_web import amber_proxy


class _FakeResponse:
    status_code = 200

    def json(self):
        return []


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        del args, kwargs
        self.run_timeout = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        del exc_type, exc, tb

    async def post(self, url, json=None, timeout=None):
        if url.endswith("/run"):
            self.run_timeout = timeout
        return _FakeResponse()


def test_send_message_uses_shared_adk_timeout(monkeypatch):
    fake_client = _FakeAsyncClient()

    monkeypatch.setattr(amber_proxy, "ensure_session", lambda *args, **kwargs: asyncio.sleep(0, result=True))
    monkeypatch.setattr(amber_proxy.httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    asyncio.run(amber_proxy.send_message("user", "session", "hello"))

    assert fake_client.run_timeout == amber_proxy.HTTP_TIMEOUT_ADK_RUN

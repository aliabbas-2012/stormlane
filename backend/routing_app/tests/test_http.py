import asyncio

import httpx
import pytest

from routing_app.providers.http import ProviderError, get_json

from .helpers import mock_client


def _run(responses: list[httpx.Response | Exception]) -> tuple[object, int]:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        item = responses[min(calls, len(responses) - 1)]
        calls += 1
        if isinstance(item, Exception):
            raise item
        return item

    async def go() -> object:
        async with mock_client(handler) as client:
            return await get_json(client, "test", "https://example.test/x")

    try:
        return asyncio.run(go()), calls
    except ProviderError as exc:
        return exc, calls


def test_success_first_try() -> None:
    assert _run([httpx.Response(200, json={"ok": 1})]) == ({"ok": 1}, 1)


def test_retries_once_on_5xx_then_succeeds() -> None:
    assert _run([httpx.Response(503), httpx.Response(200, json=[1])]) == ([1], 2)


@pytest.mark.parametrize(
    ("responses", "code"),
    [
        ([httpx.Response(502)], "bad_response"),
        ([httpx.Response(429)], "rate_limited"),
        ([httpx.ConnectError("boom")], "unavailable"),
    ],
)
def test_gives_up_after_one_retry(responses: list[httpx.Response | Exception], code: str) -> None:
    result, calls = _run(responses)
    assert isinstance(result, ProviderError)
    assert result.code == code
    assert calls == 2


def test_client_errors_are_not_retried() -> None:
    result, calls = _run([httpx.Response(400, text="bad coords")])
    assert isinstance(result, ProviderError)
    assert calls == 1


def test_invalid_json_is_a_provider_error() -> None:
    result, _ = _run([httpx.Response(200, text="<html>")])
    assert isinstance(result, ProviderError)

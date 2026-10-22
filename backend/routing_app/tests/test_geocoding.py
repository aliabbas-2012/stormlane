import asyncio
from typing import Any

import httpx

from routing_app.providers.geocoding import Place, geocode


def _photon(features: list[dict]) -> dict:
    return {
        "features": [
            {"properties": p, "geometry": {"coordinates": [p.pop("_lon", 0), p.pop("_lat", 0)]}}
            for p in features
        ]
    }


def _run(handler: Any) -> list[Place]:
    async def go() -> list[Place]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await geocode(client, "  Paris ")

    return asyncio.run(go())


def test_photon_lists_us_results_first_with_readable_labels() -> None:
    body = _photon(
        [
            {"name": "Paris", "countrycode": "FR", "_lat": 48.8, "_lon": 2.3},
            {"name": "Paris", "state": "Texas", "countrycode": "US", "_lat": 33.6, "_lon": -95.5},
            {"housenumber": "5", "street": "Main St", "city": "Paris", "state": "Tennessee",
             "countrycode": "US", "_lat": 36.3, "_lon": -88.3},
        ]
    )  # fmt: skip
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=body)

    places = _run(handler)
    assert [p.label for p in places] == ["Paris, Texas", "5 Main St, Paris, Tennessee", "Paris, FR"]
    assert places[0] == Place("Paris, Texas", 33.6, -95.5)
    assert seen[0].url.host == "photon.komoot.io"
    assert seen[0].url.params["q"] == "paris"
    assert "lat" in seen[0].url.params  # US location bias.


def test_tomtom_is_primary_and_falls_back_to_photon(settings: Any) -> None:
    settings.TOMTOM_API_KEY = "k"
    hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        if request.url.host == "api.tomtom.com":
            return httpx.Response(403)
        return httpx.Response(
            200, json=_photon([{"name": "Paris", "countrycode": "US", "state": "Texas"}])
        )

    assert [p.label for p in _run(handler)] == ["Paris, Texas"]
    assert hosts == ["api.tomtom.com", "photon.komoot.io"]


def test_tomtom_results_are_parsed(settings: Any) -> None:
    settings.TOMTOM_API_KEY = "k"
    body = {
        "results": [
            {"type": "Geography", "address": {"freeformAddress": "Paris, TX", "countryCode": "US"},
             "position": {"lat": 33.66, "lon": -95.55}},
        ]
    }  # fmt: skip

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["typeahead"] == "true"
        return httpx.Response(200, json=body)

    assert _run(handler) == [Place("Paris, TX", 33.66, -95.55)]


def test_results_are_cached() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=_photon([{"name": "Paris", "countrycode": "US"}]))

    _run(handler)
    _run(handler)
    assert calls == 1

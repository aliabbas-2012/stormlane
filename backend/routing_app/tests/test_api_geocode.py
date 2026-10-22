from typing import Any

import pytest
from django.test import Client

from routing_app.api import views
from routing_app.providers.geocoding import Place


def test_geocode_returns_places(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(client: Any, query: str) -> list[Place]:
        return [Place("Denver, Colorado", 39.74, -104.98)]

    monkeypatch.setattr(views, "geocode", fake)
    response = Client().get("/api/geocode", {"q": "denv"})
    assert response.status_code == 200
    assert response.json() == [{"label": "Denver, Colorado", "lat": 39.74, "lon": -104.98}]


@pytest.mark.parametrize("q", ["", "a", "x" * 201])
def test_geocode_validates_query(q: str) -> None:
    response = Client().get("/api/geocode", {"q": q})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"

from django.test import Client


def test_health_ok() -> None:
    response = Client().get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_method_uses_error_shape() -> None:
    response = Client().post("/api/health")
    assert response.status_code == 405
    body = response.json()
    assert body["error"]["code"] == "method_not_allowed"
    assert body["error"]["message"]

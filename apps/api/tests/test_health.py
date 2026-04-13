def test_healthz_returns_ok(client) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api"}


def test_readyz_returns_ok(client) -> None:
    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "api",
        "checks": {
            "database": {"ok": True, "detail": None},
            "redis": {"ok": True, "detail": None},
            "worker_images": {
                "ok": True,
                "detail": "Image validation skipped outside docker launch mode",
            },
        },
    }


def test_readyz_returns_503_when_redis_is_unavailable(client, app_state) -> None:
    class BrokenRedis:
        def ping(self) -> bool:
            raise RuntimeError("redis unavailable")

        def close(self) -> None:
            return None

    app_state.state.redis_client = BrokenRedis()

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"]["redis"] == {
        "ok": False,
        "detail": "redis unavailable",
    }

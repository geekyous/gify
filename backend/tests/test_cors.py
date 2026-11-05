"""CORS 白名单测试（生产跨域，凭证依赖精确 Allow-Origin）。"""

ALLOWED_ORIGIN = "http://localhost:5173"


async def test_preflight_allows_whitelisted_origin(client):
    resp = await client.options(
        "/api/auth/login",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert resp.headers["access-control-allow-credentials"] == "true"


async def test_preflight_rejects_unknown_origin(client):
    resp = await client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    # 白名单外来源不放行：不返回 Allow-Origin（浏览器将拦截响应）
    assert "access-control-allow-origin" not in resp.headers


async def test_actual_request_carries_cors_headers(client):
    resp = await client.get("/api/health", headers={"Origin": ALLOWED_ORIGIN})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == ALLOWED_ORIGIN

"""认证流程测试"""

from conftest import INITIAL_ADMIN, create_user_direct, login

# 登录锁定阈值与配置一致（5 次、10 分钟）
MAX_ATTEMPTS = 5


async def test_initial_admin_seeded_and_must_change_password(client):
    """空库启动自动创建初始管理员，首登强制改密标志为真"""
    resp = await login(client, *INITIAL_ADMIN)
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["role"] == "admin"
    assert body["data"]["mustChangePassword"] is True
    assert "gify_session" in resp.cookies


async def test_login_wrong_password(client):
    await create_user_direct("alice", password="Passw0rd!")
    resp = await login(client, "alice", "wrong-password")
    assert resp.status_code == 401
    assert resp.json()["code"] == 2001


async def test_login_lockout_after_repeated_failures(client):
    await create_user_direct("bob", password="Passw0rd!")
    for _ in range(MAX_ATTEMPTS):
        resp = await login(client, "bob", "wrong-password")
        assert resp.status_code == 401
    resp = await login(client, "bob", "Passw0rd!")  # 锁定期间正确口令也拒绝
    assert resp.status_code == 403
    assert resp.json()["code"] == 2005


async def test_login_disabled_user(client):
    await create_user_direct("carol", password="Passw0rd!", enabled=False)
    resp = await login(client, "carol", "Passw0rd!")
    assert resp.status_code == 403
    assert resp.json()["code"] == 2002


async def test_me_requires_login(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json()["code"] == 2003


async def test_logout_invalidates_session(client):
    await create_user_direct("dave", password="Passw0rd!")
    assert (await login(client, "dave", "Passw0rd!")).status_code == 200
    assert (await client.get("/api/auth/me")).status_code == 200
    resp = await client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_change_password_wrong_old(client):
    await create_user_direct("erin", password="Passw0rd!")
    await login(client, "erin", "Passw0rd!")
    resp = await client.post(
        "/api/auth/change-password",
        json={"oldPassword": "wrong-old", "newPassword": "NewPassw0rd!"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 2006


async def test_change_password_success_requires_relogin(client):
    await create_user_direct("frank", password="Passw0rd!")
    await login(client, "frank", "Passw0rd!")
    resp = await client.post(
        "/api/auth/change-password",
        json={"oldPassword": "Passw0rd!", "newPassword": "NewPassw0rd!"},
    )
    assert resp.status_code == 200
    # 修改后全部会话失效，需用新口令重新登录
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (await login(client, "frank", "NewPassw0rd!")).status_code == 200
    me = (await client.get("/api/auth/me")).json()["data"]
    assert me["mustChangePassword"] is False

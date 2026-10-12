"""用户管理与权限测试（FR-01 验收标准 1、2）。"""

from conftest import create_user_direct, login, login_admin


async def test_builder_forbidden_on_user_management(client):
    """Agent 负责人访问用户管理返回 403（FR-01 验收标准 2）。"""
    await create_user_direct("builder1", password="Passw0rd!", role="builder")
    await login(client, "builder1", "Passw0rd!")
    resp = await client.get("/api/users")
    assert resp.status_code == 403
    assert resp.json()["code"] == 2004
    resp = await client.post("/api/users", json={"username": "x", "role": "user"})
    assert resp.status_code == 403
    assert resp.json()["code"] == 2004


async def test_normal_user_forbidden_on_user_management(client):
    await create_user_direct("user1", password="Passw0rd!")
    await login(client, "user1", "Passw0rd!")
    resp = await client.get("/api/users")
    assert resp.status_code == 403


async def test_admin_create_user_returns_initial_password(client):
    await login_admin(client)
    resp = await client.post(
        "/api/users",
        json={"username": "newbie", "displayName": "新同事", "role": "user"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    initial = data["initialPassword"]
    assert initial  # 未指定口令时生成随机初始口令，仅返回一次
    assert data["mustChangePassword"] is True
    # 初始口令可登录
    assert (await login(client, "newbie", initial)).status_code == 200


async def test_create_duplicate_username(client):
    await create_user_direct("dup", password="Passw0rd!")
    await login_admin(client)
    resp = await client.post("/api/users", json={"username": "dup", "role": "user"})
    assert resp.status_code == 409
    assert resp.json()["code"] == 3001


async def test_disable_user_invalidates_session_immediately(client):
    """禁用后该用户在线会话即时失效（FR-01 验收标准 1）。"""
    target = await create_user_direct("victim", password="Passw0rd!")
    await login(client, "victim", "Passw0rd!")
    victim_cookie = client.cookies.get("gify_session")
    assert victim_cookie

    # 切换为管理员执行禁用（jar 随之变为 admin 会话）
    await login_admin(client)
    resp = await client.patch(f"/api/users/{target.id}", json={"enabled": False})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["enabled"] is False

    # 用 victim 的原始 cookie 访问：服务端会话已销毁，应 401
    resp = await client.get(
        "/api/auth/me", headers={"Cookie": f"gify_session={victim_cookie}"}
    )
    assert resp.status_code == 401

    # 禁用用户也无法再次登录
    resp = await login(client, "victim", "Passw0rd!")
    assert resp.status_code == 403
    assert resp.json()["code"] == 2002


async def test_admin_cannot_disable_self(client):
    admin = await create_user_direct("root", password="Passw0rd!", role="admin")
    await login(client, "root", "Passw0rd!")
    resp = await client.patch(f"/api/users/{admin.id}", json={"enabled": False})
    assert resp.status_code == 400
    assert resp.json()["code"] == 3003


async def test_role_change_rules(client):
    """角色变更正常路径；不能修改自己的角色。"""
    await login_admin(client)
    resp = await client.post(
        "/api/users",
        json={"username": "admin2", "role": "admin", "password": "Passw0rd!"},
    )
    assert resp.status_code == 201
    admin2_id = resp.json()["data"]["id"]

    # 2 名 admin 时将 admin2 降级：仍剩操作者一名 admin，应成功
    resp = await client.patch(f"/api/users/{admin2_id}", json={"role": "user"})
    assert resp.status_code == 200
    assert resp.json()["data"]["role"] == "user"

    # 修改自己的角色被拒绝
    me = (await client.get("/api/auth/me")).json()["data"]
    resp = await client.patch(f"/api/users/{me['id']}", json={"role": "user"})
    assert resp.status_code == 400
    assert resp.json()["code"] == 3004


async def test_reset_password(client):
    target = await create_user_direct("resetee", password="Passw0rd!")
    await login(client, "resetee", "Passw0rd!")
    assert (await client.get("/api/auth/me")).status_code == 200
    await client.post("/api/auth/logout")

    await login_admin(client)
    resp = await client.post(f"/api/users/{target.id}/reset-password", json={})
    assert resp.status_code == 200, resp.text
    initial = resp.json()["data"]["initialPassword"]
    assert initial

    # 新口令可登录且要求改密
    resp = await login(client, "resetee", initial)
    assert resp.status_code == 200
    assert resp.json()["data"]["mustChangePassword"] is True


async def test_order_by_whitelist(client):
    await login_admin(client)
    resp = await client.get("/api/users", params={"orderBy": "passwordHash"})
    assert resp.status_code == 400
    resp = await client.get(
        "/api/users", params={"orderBy": "createdAt", "order": "desc"}
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert {"items", "total", "page", "pageSize"} <= set(body)


async def test_pagination_contract(client):
    await login_admin(client)
    for i in range(3):
        await client.post("/api/users", json={"username": f"p{i}", "role": "user"})
    resp = await client.get("/api/users", params={"page": 1, "pageSize": 2})
    body = resp.json()["data"]
    assert body["total"] == 4  # seed admin + 3
    assert len(body["items"]) == 2
    assert body["pageSize"] == 2

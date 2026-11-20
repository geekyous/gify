# Web 链路知识 QA

本整理来自测试环境上的实测讨论（2026-11），每个结论都对应一次可复现的实验。复习时建议对照文末的复现命令。

## 一、CORS（CORS_ORIGINS）

**Q1：跨域拦截是前端做的还是后端做的？**

都不是，是浏览器。后端对任何来源的请求都照常执行（实测：伪造 Origin 请求照样返回 HTTP 200），区别只在白名单内的响应多一个 `access-control-allow-origin` 承诺头。浏览器验承诺：不合规就扣下响应不给 JS。简单请求（GET、普通表单 POST）扣的是**响应**；复杂请求（`Content-Type: application/json` 的 POST 等）先发 **OPTIONS 预检**，预检不过连真请求都不发。

**Q2：后端按什么判断放行谁？**

按请求头 **Origin**（协议 + 域名 + 端口的整体，与 IP 无关）比对 `CORS_ORIGINS` 白名单。命中 → 响应回显 `access-control-allow-origin: <精确来源>`。注意 `access-control-allow-credentials: true` 是无条件发出的**副锁**，只在请求声明要带凭据时浏览器才检查它；**主锁是 allow-origin 的精确匹配**，两锁齐开才放行。

**Q3：为什么不能配 `*`？**

带凭据（cookie）时浏览器要求精确 Origin 与 `credentials: true` 成对出现，`*` 与凭据互斥。

**Q4：curl、Postman、服务器之间调用受 CORS 限制吗？**

不受。没有浏览器就没有执行者。所以 CORS **不是访问控制**——它不阻止请求被处理，只阻止“恶意页面在用户浏览器里借用户身份读响应”。

## 二、SameSite（COOKIE_SAMESITE）

**Q5：SameSite 管什么？**

cookie 的“出仓检查”。策略由服务器写在 `Set-Cookie` 属性里，执行全在浏览器：发每个请求前，浏览器决定这个 cookie **放不放**进请求头。

**Q6：lax、strict、none 的区别？**

- `lax`（默认）：跨站请求不带 cookie，唯一例外是顶层 GET 导航（点链接跳转）
- `strict`：连顶层导航都不带
- `none`：跨站也带，强制要求 Secure（仅 HTTPS）

**Q7：站点（site）和源（origin）的区别？**

源 = 协议 + 域名 + 端口（CORS 用这把尺）；站 = 注册域 eTLD+1（SameSite 用这把尺）。`test.gify.geekyous.cn` 与 `test.api.gify.geekyous.cn` **跨源但同站**。本平台前端与 API 正是这种关系：需要 CORS 白名单（跨源），但 `lax` 够用（同站 cookie 无障碍）。`xxx.pages.dev` 与 `geekyous.cn` 跨站，`lax` 下 cookie 不随请求发送——所以 Pages 前端必须绑同注册域的自定义域（或改 `none`）。

**Q8：SameSite 防什么？**

CSRF。恶意网站诱导浏览器向 API 发请求时，登录 cookie 不许跟去，请求到达时是匿名身份，翻不起浪。

## 三、Nginx server_name

**Q9：server_name 的作用？**

虚拟主机路由。请求到达后，nginx 按请求头 **Host** 与各 server 块的 `server_name` 匹配，命中即走该块配置（gateway 据此把同一 443 端口的流量分给 frontend 和 app 两个容器）。

**Q10：不匹配的 Host 会怎样？**

不会拒绝，落 **default server**——该端口的第一个块（或显式标注 `default_server` 者）。实测伪造 Host 的请求被转进了 API 容器（返回 FastAPI 的 404）。想拒掉未知 Host，需专门写一个 `return 444` 的 default_server 块（444 = 不回响应直接断连）。

**Q11：server_name 是 DNS 吗？是安全边界吗？**

都不是。DNS 在请求到达前完成域名到 IP 的解析；server_name 只决定到达后归哪份配置。它也不拒绝未知 Host（见 Q10）。

**Q12：SNI 和 Host 什么关系？**

HTTPS 有两轮按名字匹配：TLS 握手阶段客户端用 **SNI** 报名，nginx 据此选证书；HTTP 阶段按 **Host** 头定路由。两者通常一致但可以不一致（可伪造 Host 过证书关），最终路由以 Host 为准。

## 四、一条请求的全景

**Q13：从输入网址到拿到响应，经过哪些判断？**

| 顺位 | 机制 | 依据 | 回答的问题 |
|---|---|---|---|
| 1 | DNS | 域名 → IP | 哪台机器 |
| 2 | TLS 握手 | SNI | 出示哪张证书 |
| 3 | nginx 路由 | 请求头 Host（server_name） | 哪个服务接待 |
| 4 | CORS | 请求头 Origin（白名单比对） | 来源可不可信（响应可否被读） |
| 5 | cookie 携带 | SameSite 按注册域判断 | 身份带不带 |

口诀：**DNS 定机器，server_name 定服务，CORS 定来源，SameSite 定身份**。四层各司其职、互不替代。

## 复现命令

```bash
# Q1/Q2：恶意 Origin 与白名单 Origin 的响应头差异
curl -sD - -o /dev/null -H "Origin: https://evil.example.com" https://<API域名>/api/health
curl -sD - -o /dev/null -H "Origin: https://<前端域名>" https://<API域名>/api/health

# Q9/Q10：server_name 路由与 default server
curl -s https://<前端域名>/ | grep "<title>"                       # 命中 frontend 块
curl -s https://<前端域名>/ -H "Host: scanner.evil.example" | head -c 60   # 伪造 Host → API 块

# Q5～Q8：SameSite 对照（浏览器操作）
# 同站前端登录后 F5，看 /api/auth/me 的 Request Headers 有 Cookie、响应 200
# 跨站页面（pages.dev）登录成功后 F5，同一请求无 Cookie 头、响应 401
```

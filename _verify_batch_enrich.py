"""验证脚本：批量补齐角色/场景/分镜 + 角色 AI 补齐时性别/年龄必填

测试流程：
1. 登录获取 token
2. 取一个项目
3. 检查角色是否有空字段（age=0 或 gender=''）
4. 调 enrich-character 看 LLM 是否返回 age/gender
5. 调 enrich-characters 批量接口
"""
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000/api/v1"


def req(method, path, *, token=None, body=None):
    url = BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return -1, str(e)


def login():
    # 用之前注册的账号
    for email in ("admin@example.com", "test@example.com", "demo@lbp.local"):
        st, r = req("POST", "/auth/login", body={"email": email, "password": "pass1234"})
        if st == 200:
            print(f"✓ 登录 {email}")
            return r["access_token"]
    print("✗ 登录失败，尝试注册")
    st, r = req("POST", "/auth/register", body={
        "email": "admin@example.com", "password": "pass1234", "display_name": "admin"
    })
    if st == 200:
        return r["access_token"]
    raise SystemExit(f"无法登录/注册: {r}")


def main():
    token = login()

    # 1. 找第一个项目
    st, r = req("GET", "/projects?limit=5", token=token)
    if st != 200:
        print(f"列项目失败: {st} {r}")
        return
    items = r.get("items", [])
    if not items:
        print("没有项目，先创建一个")
        return
    pid = items[0]["id"]
    print(f"\n使用项目 #{pid}: {items[0].get('name')}")

    # 2. 取该项目的角色列表
    st, chars = req("GET", f"/projects/{pid}/characters", token=token)
    print(f"角色列表 status={st} count={len(chars) if isinstance(chars, list) else 'N/A'}")

    # 3. 找一个有空字段的角色测试单点补齐
    target = None
    if isinstance(chars, list):
        for c in chars:
            if (c.get("age") in (0, None, "")) or (not c.get("gender")):
                target = c
                break
        if not target and chars:
            target = chars[0]

    if target:
        cid = target["id"]
        print(f"\n→ 测试 enrich-character id={cid} name={target.get('name')}")
        print(f"  补齐前: age={target.get('age')} gender={target.get('gender')!r} role={target.get('role')!r}")
        st, r = req("POST", f"/characters/{cid}/enrich", token=token)
        print(f"  status={st}")
        if st == 200:
            ch = r.get("character", {})
            print(f"  补齐后: age={ch.get('age')} gender={ch.get('gender')!r} role={ch.get('role')!r}")
            print(f"  filled={r.get('filled')}")
            if ch.get("age", 0) < 1:
                print("  ⚠️ age 仍为 0 或负数，未正确补齐")
            if not ch.get("gender"):
                print("  ⚠️ gender 仍为空，未正确补齐")
            else:
                print("  ✓ gender 已补齐")
        else:
            print(f"  ✗ 失败: {r}")

    # 4. 测试批量补齐
    print(f"\n→ 测试批量补齐角色 /projects/{pid}/enrich-characters")
    st, r = req("POST", f"/projects/{pid}/enrich-characters", token=token)
    print(f"  status={st} result={r}")

    print(f"\n→ 测试批量补齐场景 /projects/{pid}/enrich-scenes")
    st, r = req("POST", f"/projects/{pid}/enrich-scenes", token=token)
    print(f"  status={st} result={r}")

    print(f"\n→ 测试批量补齐分镜 /projects/{pid}/enrich-shots")
    st, r = req("POST", f"/projects/{pid}/enrich-shots", token=token)
    print(f"  status={st} result={r}")


if __name__ == "__main__":
    main()
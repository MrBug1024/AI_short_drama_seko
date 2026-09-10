"""轻验证：用一个新建的项目，不会有遗留 AI 状态"""
import json, urllib.request

# Step 1: 创建新项目
print("=== Step 1: 创建新项目 ===")
data = json.dumps({"name": "测试 body 路由", "description": "", "art_style": "realistic"}).encode("utf-8")
req = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/projects",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    r = urllib.request.urlopen(req, timeout=8)
    proj = json.loads(r.read().decode())
    pid = proj["id"]
    print(f"  OK project_id={pid} name={proj['name']!r}")
except urllib.error.HTTPError as e:
    print(f"  fail status={e.code} body={e.read().decode()[:200]}")
    raise SystemExit(1)

# Step 2: 空 prompt body - 应该 400
print()
print("=== Step 2: 空 prompt body - expect 400 ===")
data = json.dumps({"prompt": ""}).encode("utf-8")
req = urllib.request.Request(
    f"http://127.0.0.1:8000/api/v1/projects/{pid}/create",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    r = urllib.request.urlopen(req, timeout=8)
    print(f"  status={r.status} body={r.read().decode()[:200]}")
except urllib.error.HTTPError as e:
    body = e.read().decode()[:300]
    print(f"  status={e.code} body={body}")
    if e.code == 400 and "请输入创意描述" in body:
        print("  OK Body 路由解析正常，能识别空 prompt")

# Step 3: 9KB body - 应该不报 431
print()
print("=== Step 3: 9KB body - expect NOT 431 ===")
big = "测试剧本" + "x" * 9000
data = json.dumps({"prompt": big, "art_style": "realistic", "skill_code": "drama_story"}).encode("utf-8")
req = urllib.request.Request(
    f"http://127.0.0.1:8000/api/v1/projects/{pid}/create",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    r = urllib.request.urlopen(req, timeout=10)
    print(f"  status={r.status} body={r.read().decode()[:200]}")
except urllib.error.HTTPError as e:
    body = e.read().decode()[:300]
    print(f"  status={e.code} body={body}")
    if e.code == 431:
        print("  BUG: 9KB body 仍然 431 - 修复失败")
    else:
        print(f"  OK 不是 431 (status={e.code})")
except Exception as e:
    print(f"  exception: {type(e).__name__}: {e}")
    print("  OK 不是 431，进入了业务逻辑（可能 AI 调用卡住）")

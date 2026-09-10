"""验证 /create body 提交"""
import json, urllib.request, urllib.parse

big_prompt = "测试创意" + "x" * 9000

# 试 1：query 形式（应 431）
print("=== Test 1: query string ~9KB prompt (expect 431) ===")
try:
    req = urllib.request.Request(
        f"http://127.0.0.1:8000/api/v1/projects/1/create?prompt={urllib.parse.quote(big_prompt)}",
        method="POST",
    )
    r = urllib.request.urlopen(req, timeout=8)
    print(f"  status={r.status}")
    print(f"  body: {r.read().decode()[:150]}")
except urllib.error.HTTPError as e:
    print(f"  status={e.code} body: {e.read().decode()[:150]}")
except Exception as e:
    print(f"  exception: {type(e).__name__}: {e}")

# 试 2：body 形式（应 200）
print()
print("=== Test 2: JSON body ~9KB prompt (expect 200) ===")
data = json.dumps({"prompt": big_prompt, "art_style": "", "skill_code": "drama_story"}).encode("utf-8")
req = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/projects/1/create",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    r = urllib.request.urlopen(req, timeout=10)
    print(f"  status={r.status} SUCCESS")
    print(f"  body: {r.read().decode()[:150]}")
except urllib.error.HTTPError as e:
    print(f"  status={e.code} body: {e.read().decode()[:150]}")
except Exception as e:
    print(f"  exception: {type(e).__name__}: {e}")

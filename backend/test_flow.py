"""端到端测试 - 创建项目 + 启动 7 步创作"""
import requests
import json

BASE = "http://127.0.0.1:8000/api/v1"

# 1) 创建项目
r = requests.post(f"{BASE}/projects", json={
    "name": "测试短剧 - 青铜古镜",
    "description": "一个考古学教授与神秘古镜",
    "prompt": "一个年轻的考古学教授，在深夜的博物馆里发现了一件会说话的青铜古镜，由此卷入一场跨越千年的阴谋",
    "art_style": "电影感写实风格，胶片色调",
    "target_episodes": 1,
    "target_duration_sec": 90,
})
print(f"[1] 创建项目: id={r.json()['id']} status={r.json()['status']}")
pid = r.json()["id"]

# 2) 启动 7 步创作
print("[2] 启动 7 步创作...")
r2 = requests.post(f"{BASE}/projects/{pid}/create", params={
    "prompt": "一个年轻的考古学教授，在深夜的博物馆里发现了一件会说话的青铜古镜",
    "art_style": "电影感写实风格，胶片色调",
    "skill_code": "drama_story",
}, timeout=180)
d = r2.json()
print(f"    logline: {d.get('logline', '')[:120]}")
print(f"    art_style: {d.get('art_style', '')}")
print(f"    角色数: {len(d.get('characters', []))}")
print(f"    场景数: {len(d.get('scenes', []))}")
print(f"    道具数: {len(d.get('props', []))}")
print(f"    镜头数: {len(d.get('shots', []))}")
print(f"    剧本预览: {(d.get('script_md', '')[:200])}")
print(f"    持久化: {d.get('persisted')}")

# 3) 查询项目状态
r3 = requests.get(f"{BASE}/projects/{pid}")
pj = r3.json()
print(f"\n[3] 项目状态: status={pj['status']}  角色:{pj['character_count']} 场景:{pj['scene_count']} 镜头:{pj['shot_count']}")

# 4) 列出任务
r4 = requests.get(f"{BASE}/generation/tasks", params={"project_id": pid})
tasks = r4.json()
print(f"\n[4] 任务列表 (项目 {pid}):")
for t in tasks:
    print(f"    - #{t['id']} {t['task_type']:15s} status={t['status']:10s} {t.get('target_title', '')[:30]}")

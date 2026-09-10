"""临时验证脚本：检查 canvas 接口返回"""
import json, urllib.request

with urllib.request.urlopen("http://127.0.0.1:8000/api/v1/projects/1/canvas") as r:
    d = json.loads(r.read().decode("utf-8"))

print(f"node count: {len(d['nodes'])}")
for n in d["nodes"][:10]:
    title = n.get("title") or ""
    meta = n.get("meta") or {}
    extra = ""
    if n["node_type"] == "character":
        extra = f"name={meta.get('name','')!r} alias={meta.get('alias','')!r}"
    elif n["node_type"] == "scene":
        extra = f"name={meta.get('name','')!r} loc={meta.get('location','')!r}"
    elif n["node_type"] == "shot":
        desc = meta.get("description", "")
        if len(desc) > 40:
            desc = desc[:40] + "..."
        extra = f"code={meta.get('shot_code','')!r} desc={desc!r}"
    print(f"  type={n['node_type']:9} title={title!r:25} | {extra}")

"""看 shot 的创建时间，对应哪次创建"""
import sqlite3
c = sqlite3.connect('backend/data/seko.db')
print("=" * 80)
print("[所有 shot 按创建时间]")
print("=" * 80)
for r in c.execute("""
    SELECT id, shot_code, scene_id, character_ids,
           substr(description, 1, 50) as desc,
           created_at, updated_at
    FROM shots WHERE project_id=1
    ORDER BY created_at
"""):
    print(f"#{r[0]:3} {r[1]:6} scene={r[2]} chars={r[3]} | {r[4]:50} | {r[5]}")

print()
print("=" * 80)
print("[所有 canvas 节点（按创建时间）]")
print("=" * 80)
for r in c.execute("""
    SELECT id, node_type, ref_id, title, created_at
    FROM canvas_nodes WHERE project_id=1
    ORDER BY created_at
"""):
    print(f"node#{r[0]:3} type={r[1]:9} ref={r[2]:3} title={r[3]!r:30} | {r[4]}")

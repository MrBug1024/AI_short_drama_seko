"""全面排查项目 1 的：画布节点 ↔ 数据库 shot/scene/character 关联是否对得上"""
import sqlite3, json
c = sqlite3.connect('backend/data/seko.db')
c.row_factory = sqlite3.Row

print("=" * 80)
print("[1] 数据库里的 shot（前 8 个）")
print("=" * 80)
for r in c.execute("SELECT id, project_id, shot_no, shot_code, scene_id, character_ids, description, composition, camera_movement, image_url, video_url FROM shots WHERE project_id=1 ORDER BY shot_no LIMIT 8"):
    d = dict(r)
    print(f"shot#{d['id']} {d['shot_code']} scene_id={d['scene_id']} chars={d['character_ids']}")
    print(f"  desc: {d['description'][:80]}")
    print(f"  comp={d['composition']!r} move={d['camera_movement']!r}")
    print(f"  image={'YES' if d['image_url'] else 'NO'} video={'YES' if d['video_url'] else 'NO'}")

print()
print("=" * 80)
print("[2] 数据库里的 scene（前 5 个）")
print("=" * 80)
for r in c.execute("SELECT id, project_id, name, location, time_of_day, weather, mood, description FROM scenes WHERE project_id=1 LIMIT 5"):
    d = dict(r)
    print(f"scene#{d['id']} {d['name']!r} location={d['location']!r} time={d['time_of_day']!r} weather={d['weather']!r}")
    print(f"  desc: {(d['description'] or '')[:80]}")

print()
print("=" * 80)
print("[3] 数据库里的 character（前 8 个）")
print("=" * 80)
for r in c.execute("SELECT id, project_id, name, alias, age, gender, role, appearance FROM characters WHERE project_id=1 ORDER BY id LIMIT 8"):
    d = dict(r)
    print(f"char#{d['id']} {d['name']!r} alias={d['alias']!r} age={d['age']} gender={d['gender']!r} role={d['role']!r}")
    print(f"  appearance: {(d['appearance'] or '')[:80]}")

print()
print="=" * 80
print("[4] 画布节点（shot 类型前 5 个）")
print("=" * 80)
for r in c.execute("SELECT id, project_id, node_type, ref_id, title, meta, thumbnail_url, status FROM canvas_nodes WHERE project_id=1 AND node_type='shot' ORDER BY position_y, position_x LIMIT 5"):
    d = dict(r)
    meta = d.get('meta') or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except:
            meta = {'_raw': meta[:60]}
    print(f"node#{d['id']} ref_id={d['ref_id']} title={d['title']!r}")
    print(f"  meta: {meta}")
    print(f"  thumb: {(d['thumbnail_url'] or '')[:60]}")

print()
print("=" * 80)
print("[5] shot ↔ scene ↔ character 关联一致性检查")
print("=" * 80)
# shot 有 scene_id, character_ids 字段，但实际是否真的有数据？
shots_no_scene = c.execute("SELECT COUNT(*) FROM shots WHERE project_id=1 AND (scene_id IS NULL OR scene_id=0)").fetchone()[0]
shots_no_char = c.execute("SELECT COUNT(*) FROM shots WHERE project_id=1 AND (character_ids IS NULL OR character_ids='[]' OR character_ids='')").fetchone()[0]
total_shots = c.execute("SELECT COUNT(*) FROM shots WHERE project_id=1").fetchone()[0]
print(f"shots 总数: {total_shots}")
print(f"  无 scene 关联: {shots_no_scene}")
print(f"  无 character 关联: {shots_no_char}")

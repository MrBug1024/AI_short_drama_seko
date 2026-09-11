import sqlite3
c = sqlite3.connect('data/seko.db')
print('--- canvas nodes by type ---')
for x in c.execute("select node_type, count(*) from canvas_nodes where project_id=1 group by node_type").fetchall():
    print(x)
print()
print('shots表:', c.execute('select count(*) from shots where project_id=1').fetchone()[0])
print('canvas shot:', c.execute("select count(*) from canvas_nodes where project_id=1 and node_type='shot'").fetchone()[0])
print()
print('--- character_design tasks ---')
for x in c.execute("select id, params, status, error_msg from generation_tasks where project_id=1 and task_type='character_design' limit 3").fetchall():
    print(x)
print()
print('--- image/video tasks ---')
for x in c.execute("select id, task_type, status, shot_id, model_name, error_msg from generation_tasks where project_id=1 and task_type in ('shot_image','shot_video','image','video') order by id desc limit 20").fetchall():
    print(x)
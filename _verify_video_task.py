import sqlite3
c = sqlite3.connect('data/seko.db')
print('--- task 49 ---')
for x in c.execute("select id, project_id, task_type, status, prompt, params, model_name, error_msg from generation_tasks where id=49").fetchall():
    print(x)
print()
print('--- shots in project 1 with image ---')
for x in c.execute("select id, shot_code, image_url from shots where project_id=1").fetchall():
    print(x)
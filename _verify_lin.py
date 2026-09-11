import sqlite3
c = sqlite3.connect('backend/data/seko.db')
for r in c.execute("SELECT id, name, age, gender, appearance, role FROM characters WHERE name LIKE '%林远%'"):
    print(r)
    print('--- appearance start ---')
    print(r[4])
    print('--- appearance end ---')

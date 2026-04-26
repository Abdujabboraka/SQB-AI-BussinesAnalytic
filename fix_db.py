import sqlite3
import json

try:
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('SELECT id, target_customer FROM core_businessanalysisrequest')
    rows = c.fetchall()
    for r in rows:
        tc = r[1]
        if tc:
            if not tc.startswith('[') and not tc.startswith('{') and not tc.startswith('"'):
                new_tc = json.dumps([tc])
                c.execute('UPDATE core_businessanalysisrequest SET target_customer = ? WHERE id = ?', (new_tc, r[0]))
    conn.commit()
    conn.close()
    print("DB fixed")
except Exception as e:
    print(f"Error: {e}")

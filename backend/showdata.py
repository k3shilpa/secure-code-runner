import sqlite3

conn = sqlite3.connect("code_runner.db")
cursor = conn.cursor()

# Example: show all data in code_history
cursor.execute("SELECT * FROM code_history;")
rows = cursor.fetchall()

print("Data in code_history:")
for row in rows:
    print(row)

conn.close()

import sqlite3

conn = sqlite3.connect("code_runner.db")
cursor = conn.cursor()

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

print("Tables in database:")
for t in tables:
    print("-", t[0])

# Optional: show columns of a table
for t in tables:
    cursor.execute(f"PRAGMA table_info({t[0]});")
    columns = cursor.fetchall()
    print(f"\nColumns in {t[0]}:")
    for col in columns:
        print(f" - {col[1]} ({col[2]})")

conn.close()

import sqlite3

conn = sqlite3.connect("code_runner.db")
cursor = conn.cursor()

# Add filename column if it doesn't exist
try:
    cursor.execute("ALTER TABLE code_history ADD COLUMN filename TEXT DEFAULT 'untitled';")
    print("✅ Column 'filename' added successfully!")
except sqlite3.OperationalError as e:
    print(f"⚠️ Could not add column (maybe it already exists): {e}")

# Update old entries to have 'untitled'
cursor.execute("""
UPDATE code_history
SET filename = 'untitled'
WHERE filename IS NULL OR filename = '';
""")

conn.commit()
conn.close()
print("✅ Old entries updated successfully!")

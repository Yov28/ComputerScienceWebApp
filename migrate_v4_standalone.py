"""
Standalone v4 migration — talks to the database DIRECTLY, without importing
the app or models. This avoids the chicken-and-egg crash where create_app()
runs seed_data() and queries columns that don't exist yet.

Adds (all strictly additive, no DROP/DELETE/UPDATE):
  - weeks.allow_submissions       (default TRUE)
  - submissions.feedback_file_url
  - submissions.feedback_file_name

Run locally against the LIVE database:
  DATABASE_URL="postgresql://...external-url..." python3 migrate_v4_standalone.py

Or in the Render Shell (DATABASE_URL is already set there):
  python3 migrate_v4_standalone.py
"""
import os
import psycopg2

ALTERS = [
    ("weeks",       "allow_submissions",  "ALTER TABLE weeks ADD COLUMN allow_submissions BOOLEAN DEFAULT TRUE"),
    ("submissions", "feedback_file_url",  "ALTER TABLE submissions ADD COLUMN feedback_file_url VARCHAR(600)"),
    ("submissions", "feedback_file_name", "ALTER TABLE submissions ADD COLUMN feedback_file_name VARCHAR(300)"),
]

def main():
    url = os.environ.get('DATABASE_URL')
    if not url:
        raise SystemExit("DATABASE_URL is not set. Pass it on the command line.")
    # psycopg2 needs postgresql:// not postgres://
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)

    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()

    for table, column, ddl in ALTERS:
        cur.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
            (table, column),
        )
        if cur.fetchone():
            print(f"  skip: {table}.{column} already exists")
        else:
            cur.execute(ddl)
            print(f"  added: {table}.{column}")

    cur.close()
    conn.close()
    print("Migration v4 complete. No existing data was modified.")

if __name__ == '__main__':
    main()

"""
One-time migration v4:
  - weeks.allow_submissions  (default TRUE)
  - submissions.feedback_file_url
  - submissions.feedback_file_name

STRICTLY ADDITIVE — no DROP, DELETE, or UPDATE. Safe to run more than once.
Run with:  python3 migrate_v4.py
"""
from app import create_app
from extensions import db
from sqlalchemy import text

ALTERS = [
    ("weeks",       "allow_submissions",  "ALTER TABLE weeks ADD COLUMN allow_submissions BOOLEAN DEFAULT TRUE"),
    ("submissions", "feedback_file_url",  "ALTER TABLE submissions ADD COLUMN feedback_file_url VARCHAR(600)"),
    ("submissions", "feedback_file_name", "ALTER TABLE submissions ADD COLUMN feedback_file_name VARCHAR(300)"),
]

def column_exists(conn, table, column):
    res = conn.execute(text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = :t AND column_name = :c"
    ), {"t": table, "c": column})
    return res.first() is not None

def column_exists_sqlite(conn, table, column):
    res = conn.execute(text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in res)

def main():
    app = create_app()
    with app.app_context():
        is_sqlite = db.engine.url.drivername.startswith('sqlite')
        with db.engine.begin() as conn:
            for table, column, ddl in ALTERS:
                exists = (column_exists_sqlite(conn, table, column) if is_sqlite
                          else column_exists(conn, table, column))
                if exists:
                    print(f"  skip: {table}.{column} already exists")
                else:
                    conn.execute(text(ddl))
                    print(f"  added: {table}.{column}")
        print("Migration v4 complete. No existing data was modified.")

if __name__ == '__main__':
    main()

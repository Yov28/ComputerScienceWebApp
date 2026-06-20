"""
One-time migration v3: adds the cloud_url column to the slides table so
teacher resource files can be stored on Cloudinary and persist across restarts.

STRICTLY ADDITIVE — no DROP, DELETE, or UPDATE. Safe to run more than once.

Run with:  python3 migrate_v3.py
"""
from app import create_app
from extensions import db
from sqlalchemy import text

ALTERS = [
    ("slides", "cloud_url", "ALTER TABLE slides ADD COLUMN cloud_url VARCHAR(600)"),
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
        print("Migration v3 complete. No existing data was modified.")

if __name__ == '__main__':
    main()

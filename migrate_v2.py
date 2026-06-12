"""
One-time migration: adds new columns and tables for question types,
text answers, and student work submissions.

STRICTLY ADDITIVE — contains no DROP, DELETE, or data-modifying statements.
Safe to run more than once (each change is skipped if already applied).

Run with:  python3 migrate_v2.py
"""
from app import create_app
from extensions import db
from sqlalchemy import text

ALTERS = [
    # questions: new type + optional model answer
    ("questions", "qtype",               "ALTER TABLE questions ADD COLUMN qtype VARCHAR(20) DEFAULT 'mcq'"),
    ("questions", "model_answer",        "ALTER TABLE questions ADD COLUMN model_answer TEXT"),
    # answers: multi-select, free text, marking workflow
    ("answers",   "selected_option_ids", "ALTER TABLE answers ADD COLUMN selected_option_ids VARCHAR(300)"),
    ("answers",   "text_answer",         "ALTER TABLE answers ADD COLUMN text_answer TEXT"),
    ("answers",   "pending",             "ALTER TABLE answers ADD COLUMN pending BOOLEAN DEFAULT FALSE"),
    ("answers",   "teacher_feedback",    "ALTER TABLE answers ADD COLUMN teacher_feedback TEXT"),
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
        # Creates ONLY tables that don't exist yet (e.g. submissions). Never alters existing ones.
        db.create_all()
        print("  ensured: submissions table exists")
        print("Migration complete. No existing data was modified.")

if __name__ == '__main__':
    main()

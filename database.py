import sqlite3
import os
from dotenv import load_dotenv
load_dotenv()

DB_PATH = os.getenv("DB_PATH", "news.db")


def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT,
            url        TEXT UNIQUE,
            summary    TEXT,
            source     TEXT,
            category   TEXT,
            published  TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT,
            phone      TEXT,
            keyword    TEXT NOT NULL,
            active     INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(email, keyword)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS alert_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            subscriber_id INTEGER,
            article_id    INTEGER,
            sent_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(subscriber_id, article_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS telegram_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword    TEXT,
            article_id INTEGER,
            sent_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(keyword, article_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS processing_times (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            permit_type TEXT,
            time_weeks  TEXT,
            checked_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── CRS history: now stores full draw data, not just score ──
    c.execute("""
        CREATE TABLE IF NOT EXISTS crs_history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            score        INTEGER,
            invitations  INTEGER,
            draw_type    TEXT DEFAULT 'General',
            draw_number  INTEGER,
            draw_title   TEXT,
            draw_url     TEXT,
            draw_date    TEXT,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(draw_number)
        )
    """)

    # ── Migrate old crs_history if it doesn't have new columns ──
    _migrate_crs_history(c)

    # ── Seed default subscribers (your personal keywords) ──
    default_subs = [
        ("piyugupta2279@gmail.com", "express entry"),
        ("piyugupta2279@gmail.com", "PGWP"),
        ("piyugupta2279@gmail.com", "study permit"),
        ("piyugupta2279@gmail.com", "TR to PR"),
        ("piyugupta2279@gmail.com", "Ontario PNP"),
    ]
    for email, kw in default_subs:
        try:
            c.execute(
                "INSERT OR IGNORE INTO subscribers (email, keyword, active) VALUES (?, ?, 1)",
                (email, kw)
            )
        except Exception as e:
            print(f"[db] Seed error: {e}")

    conn.commit()
    conn.close()
    print(f"[db] Tables ready at {DB_PATH}")


def _migrate_crs_history(c):
    """Add new columns to crs_history if they don't exist (safe migration)."""
    new_columns = [
        ("invitations",  "INTEGER"),
        ("draw_type",    "TEXT DEFAULT 'General'"),
        ("draw_number",  "INTEGER"),
    ]
    for col_name, col_def in new_columns:
        try:
            c.execute(f"ALTER TABLE crs_history ADD COLUMN {col_name} {col_def}")
            print(f"[db] Migrated: added column {col_name} to crs_history")
        except Exception:
            pass  # column already exists


if __name__ == "__main__":
    init_db()

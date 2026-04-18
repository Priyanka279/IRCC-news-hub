import sqlite3
import os

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
    c.execute("""
        CREATE TABLE IF NOT EXISTS crs_history (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            score      INTEGER,
            draw_title TEXT,
            draw_url   TEXT,
            draw_date  TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    print(f"[db] Tables ready at {DB_PATH}")
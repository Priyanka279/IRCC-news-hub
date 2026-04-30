import sqlite3
import os

DB_PATH = os.getenv("DB_PATH", "news.db")

def init_db():
    # ... all your CREATE TABLE statements ...

    # ── Seed default subscriber so alerts always work ──
    try:
        c.execute("""
            INSERT OR IGNORE INTO subscribers (email, keyword, active)
            VALUES (?, ?, 1)
        """, ("piyugupta2279@gmail.com", "express entry"))
        c.execute("""
            INSERT OR IGNORE INTO subscribers (email, keyword, active)
            VALUES (?, ?, 1)
        """, ("piyugupta2279@gmail.com", "PGWP"))
        c.execute("""
            INSERT OR IGNORE INTO subscribers (email, keyword, active)
            VALUES (?, ?, 1)
        """, ("piyugupta2279@gmail.com", "study permit"))
        c.execute("""
            INSERT OR IGNORE INTO subscribers (email, keyword, active)
            VALUES (?, ?, 1)
        """, ("piyugupta2279@gmail.com", "TR to PR"))
        c.execute("""
            INSERT OR IGNORE INTO subscribers (email, keyword, active)
            VALUES (?, ?, 1)
        """, ("piyugupta2279@gmail.com", "Ontario PNP"))
    except Exception as e:
        print(f"[db] Seed subscriber error: {e}")

    conn.commit()
    conn.close()
    print(f"[db] Tables ready at {DB_PATH}")
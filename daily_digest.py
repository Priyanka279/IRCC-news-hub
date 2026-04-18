import sqlite3
from datetime import datetime, timedelta
from telegram_alerts import send_telegram
from dotenv import load_dotenv
load_dotenv()
import os
DB_PATH = os.getenv("DB_PATH", "news.db")

def send_daily_digest():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    since = (datetime.now() - timedelta(hours=24)).isoformat()
    c.execute("""
        SELECT * FROM articles
        WHERE created_at >= ?
        ORDER BY category, created_at DESC
    """, (since,))
    articles = [dict(row) for row in c.fetchall()]
    conn.close()

    if not articles:
        print("[digest] No new articles in last 24h.")
        return

    grouped = {}
    for a in articles:
        cat = a["category"] or "General"
        grouped.setdefault(cat, []).append(a)

    now = datetime.now().strftime("%B %d, %Y")
    msg = f"🍁 *IRCC Daily Digest — {now}*\n"
    msg += f"_{len(articles)} new articles in the last 24 hours_\n\n"

    for cat, items in grouped.items():
        msg += f"*{cat}* ({len(items)})\n"
        for a in items[:3]:
            msg += f"• [{a['title']}]({a['url']})\n"
        msg += "\n"

    msg += "_Visit your IRCC News Hub for full coverage_"
    send_telegram(msg)
    print(f"[digest] Sent digest with {len(articles)} articles.")

if __name__ == "__main__":
    send_daily_digest()
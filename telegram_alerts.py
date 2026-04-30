import os
import sqlite3
import requests
from dotenv import load_dotenv
load_dotenv()

DB_PATH = os.getenv("DB_PATH", "news.db")

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def send_telegram(message: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[telegram] Credentials not set. Skipping.")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        res = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }, timeout=10)
        res.raise_for_status()
        print("[telegram] Message sent.")
        return True
    except Exception as e:
        print(f"[telegram] Error: {e}")
        return False

def check_and_send_telegram_alerts():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return

    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT DISTINCT keyword FROM subscribers WHERE active = 1")
    keywords = [row["keyword"] for row in c.fetchall()]

    for keyword in keywords:
        kw = keyword.lower()
        c.execute("""
            SELECT a.* FROM articles a
            WHERE (LOWER(a.title) LIKE ? OR LOWER(a.summary) LIKE ?)
              AND a.id NOT IN (
                SELECT article_id FROM telegram_log WHERE keyword = ?
              )
            ORDER BY a.created_at DESC LIMIT 5
        """, (f"%{kw}%", f"%{kw}%", kw))

        articles = [dict(row) for row in c.fetchall()]
        if not articles:
            continue

        msg = f"🍁 *IRCC Alert* — `{keyword}`\n\n"
        for a in articles:
            msg += f"📌 *{a['title']}*\n"
            msg += f"_{a['source']} · {a['category']}_\n"
            msg += f"{a['url']}\n\n"

        send_telegram(msg)

        for a in articles:
            try:
                c.execute(
                    "INSERT OR IGNORE INTO telegram_log (keyword, article_id) VALUES (?, ?)",
                    (kw, a["id"])
                )
            except Exception:
                pass
        conn.commit()

    conn.close()
    print("[telegram] Alert check complete.")

def send_draw_alert(title: str, url: str, crs: str = None):
    msg = "🔥 *New Express Entry Draw Detected!*\n\n"
    msg += f"*{title}*\n"
    if crs:
        msg += f"CRS Cutoff: `{crs}`\n"
    msg += f"\n{url}"
    send_telegram(msg)

def send_latest_news_digest():
    """Send last 5 new articles directly to your Telegram — no subscriber needed."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Get articles from last 30 min not yet sent
    c.execute("""
        SELECT * FROM articles
        WHERE created_at >= datetime('now', '-30 minutes')
        ORDER BY created_at DESC LIMIT 5
    """)
    articles = [dict(row) for row in c.fetchall()]
    conn.close()

    if not articles:
        return

    msg = f"🍁 *{len(articles)} new IRCC articles*\n\n"
    for a in articles:
        msg += f"📌 *{a['title']}*\n"
        msg += f"_{a['source']} · {a['category']}_\n"
        msg += f"{a['url']}\n\n"
    send_telegram(msg)

if __name__ == "__main__":
    send_telegram("✅ IRCC News Hub Telegram alerts are working!")
import feedparser
import os
import sqlite3
import re
import threading
from telegram_alerts import send_draw_alert

_db_lock = threading.Lock()
DB_PATH = os.getenv("DB_PATH", "news.db")

RSS_SOURCES = [
    {
        "url": "https://www.canada.ca/en/immigration-refugees-citizenship/news/notices.atom",
        "source": "IRCC Official",
        "category": "IRCC Updates"
    },
    {
        "url": "https://www.canada.ca/en/immigration-refugees-citizenship/news.atom",
        "source": "IRCC Official",
        "category": "IRCC Updates"
    },
    {
        "url": "https://www.cicnews.com/feed",
        "source": "CIC News",
        "category": "General"
    },
    {
        "url": "https://www.immigration.ca/feed",
        "source": "Immigration.ca",
        "category": "General"
    },
    {
        "url": "https://moving2canada.com/feed/",
        "source": "Moving2Canada",
        "category": "General"
    },
    {
        "url": "https://canadaimmigrants.com/feed/",
        "source": "Canada Immigrants",
        "category": "General"
    },
    {
        "url": "https://globalnews.ca/tag/immigration/feed/",
        "source": "Global News",
        "category": "General"
    },
]

CATEGORY_KEYWORDS = {
    "Express Entry":  ["express entry", "crs", "comprehensive ranking", "draw", "tie-breaking"],
    "PNP Programs":   ["provincial nominee", "pnp", "oinp", "sinp", "mpnp", "bcpnp"],
    "Intl Students":  ["international student", "study permit", "pgwp", "post-graduation", "student visa"],
    "TRP / PR":       ["temporary resident permit", "trp", "permanent resident", "permanent residence"],
    "Work Permits":   ["work permit", "lmia", "open work permit", "closed work permit"],
    "IRCC Updates":   ["ircc", "immigration refugees", "citizenship canada"],
}

CRS_PATTERN   = re.compile(r'\b(crs|score)[^\d]*(\d{3})\b', re.IGNORECASE)
DRAW_KEYWORDS = ["express entry draw", "invitation to apply", "ita issued",
                 "crs cut-off", "draw #", "rounds of invitations"]

def categorize(title, summary):
    text = (title + " " + summary).lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return "General"

def extract_crs(title, summary):
    match = CRS_PATTERN.search(title + " " + summary)
    return match.group(2) if match else None

def is_draw_article(title):
    t = title.lower()
    return any(kw in t for kw in DRAW_KEYWORDS)

def fetch_rss():
    entries_to_insert = []
    for source in RSS_SOURCES:
        try:
            feed = feedparser.parse(source["url"])
            for entry in feed.entries:
                title   = entry.get("title", "").strip()
                url     = entry.get("link", "").strip()
                summary = entry.get("summary", "")[:500].strip()
                pub     = entry.get("published", "")
                if not title or not url:
                    continue
                category = categorize(title, summary)
                crs      = extract_crs(title, summary)
                if crs:
                    summary = f"[CRS: {crs}] " + summary
                entries_to_insert.append((title, url, summary, source["source"], category, pub, crs))
        except Exception as e:
            print(f"[fetcher] Error fetching {source['source']}: {e}")

    with _db_lock:
        try:
            conn = sqlite3.connect(DB_PATH, timeout=30)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            c = conn.cursor()
            inserted = 0
            for entry in entries_to_insert:
                title, url, summary, source, category, pub, crs = entry
                try:
                    c.execute("""
                        INSERT OR IGNORE INTO articles
                            (title, url, summary, source, category, published)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (title, url, summary, source, category, pub))
                    if c.rowcount > 0:
                        inserted += 1
                        # Save CRS score to history table
                        if crs and category == "Express Entry":
                            c.execute("""
                                INSERT OR IGNORE INTO crs_history
                                    (score, draw_title, draw_url, draw_date)
                                VALUES (?, ?, ?, ?)
                            """, (int(crs), title, url, pub))
                        # Send instant Telegram alert for new draw articles
                        if is_draw_article(title):
                            try:
                                send_draw_alert(title, url, crs)
                            except Exception:
                                pass
                except Exception as e:
                    print(f"[fetcher] Insert error: {e}")
            conn.commit()
            conn.close()
            print(f"[fetcher] Done. {inserted} new articles inserted.")
        except Exception as e:
            print(f"[fetcher] DB error: {e}")
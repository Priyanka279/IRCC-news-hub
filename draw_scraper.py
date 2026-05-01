"""
draw_scraper.py

Scrapes Express Entry draw results directly from the IRCC official page.
More reliable than RSS for draw data since IRCC posts structured tables.
Also scrapes the Canada.ca EE rounds page as a fallback.
"""
import requests
import sqlite3
import os
import re
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

DB_PATH = os.getenv("DB_PATH", "news.db")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# IRCC official Express Entry rounds of invitations page
DRAWS_URL = "https://www.canada.ca/en/immigration-refugees-citizenship/corporate/mandate/policies-operational-instructions-agreements/ministerial-instructions/express-entry-rounds.html"


def scrape_draws():
    """
    Scrape Express Entry draw history from IRCC's official page.
    Returns list of draw dicts with: number, date, type, crs_score, invitations
    """
    draws = []
    try:
        res = requests.get(DRAWS_URL, headers=HEADERS, timeout=30)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        # IRCC uses a table with class "table" for draw data
        table = soup.find("table")
        if not table:
            print("[draws] No table found on IRCC page.")
            return []

        rows = table.find_all("tr")
        for row in rows[1:]:  # skip header
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 4:
                continue

            # Columns: No. | Date | Type | CRS Score | Invitations Issued
            draw = {
                "number":      _clean_int(cells[0]),
                "date":        _parse_date(cells[1]),
                "draw_type":   cells[2] if len(cells) > 2 else "General",
                "crs_score":   _clean_int(cells[3]) if len(cells) > 3 else None,
                "invitations": _clean_int(cells[4]) if len(cells) > 4 else None,
                "url":         DRAWS_URL,
            }
            if draw["crs_score"] and draw["crs_score"] > 200:
                draws.append(draw)

    except Exception as e:
        print(f"[draws] Scrape error: {e}")

    print(f"[draws] Found {len(draws)} draws from IRCC page.")
    return draws


def _clean_int(val: str) -> int | None:
    """Extract integer from string like '567' or '4,500'"""
    if not val:
        return None
    cleaned = re.sub(r"[^\d]", "", val)
    return int(cleaned) if cleaned else None


def _parse_date(val: str) -> str:
    """Try to parse date strings like 'April 17, 2025' or '2025-04-17'"""
    val = val.strip()
    formats = ["%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return val  # return as-is if unparseable


def save_draws_to_db(draws: list):
    """Save draws to crs_history table, skipping duplicates."""
    if not draws:
        return 0

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    c = conn.cursor()
    inserted = 0

    for draw in draws:
        try:
            c.execute("""
                INSERT OR IGNORE INTO crs_history
                    (score, invitations, draw_type, draw_number, draw_title, draw_url, draw_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                draw.get("crs_score"),
                draw.get("invitations"),
                draw.get("draw_type", "General"),
                draw.get("number"),
                f"Express Entry Draw #{draw.get('number', '?')} — CRS {draw.get('crs_score', '?')}",
                draw.get("url", DRAWS_URL),
                draw.get("date", "")
            ))
            if c.rowcount:
                inserted += 1
        except Exception as e:
            print(f"[draws] Insert error: {e}")

    conn.commit()
    conn.close()
    print(f"[draws] {inserted} new draws saved.")
    return inserted


def get_latest_draw() -> dict | None:
    """Return the most recent draw from DB."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT * FROM crs_history
        ORDER BY draw_date DESC, draw_number DESC
        LIMIT 1
    """)
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_draw_stats() -> dict:
    """
    Return summary stats useful for the frontend:
    - latest cutoff score
    - latest draw number
    - invitations in latest draw
    - days since last draw
    - average draw frequency (days)
    - trend (rising/falling/stable CRS over last 5 draws)
    - estimated next draw date
    """
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT * FROM crs_history
        WHERE score IS NOT NULL AND score > 200
        ORDER BY draw_date DESC, draw_number DESC
        LIMIT 20
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    if not rows:
        return {
            "latest_cutoff": None,
            "latest_draw_number": None,
            "latest_invitations": None,
            "days_since_draw": None,
            "avg_frequency_days": None,
            "trend": "unknown",
            "estimated_next_draw": None,
            "recent_draws": []
        }

    latest = rows[0]

    # Days since last draw
    days_since = None
    if latest.get("draw_date"):
        try:
            d = datetime.strptime(latest["draw_date"][:10], "%Y-%m-%d")
            days_since = (datetime.now() - d).days
        except Exception:
            pass

    # Average frequency between draws (last 10 draws)
    avg_freq = None
    if len(rows) >= 2:
        gaps = []
        for i in range(len(rows) - 1):
            try:
                d1 = datetime.strptime(rows[i]["draw_date"][:10], "%Y-%m-%d")
                d2 = datetime.strptime(rows[i+1]["draw_date"][:10], "%Y-%m-%d")
                gaps.append(abs((d1 - d2).days))
            except Exception:
                pass
        avg_freq = round(sum(gaps) / len(gaps)) if gaps else None

    # Estimated next draw
    est_next = None
    if avg_freq and latest.get("draw_date"):
        try:
            last_d = datetime.strptime(latest["draw_date"][:10], "%Y-%m-%d")
            from datetime import timedelta
            est_next = (last_d + timedelta(days=avg_freq)).strftime("%Y-%m-%d")
        except Exception:
            pass

    # CRS trend: compare last 5 draws
    scores = [r["score"] for r in rows[:5] if r.get("score")]
    trend = "unknown"
    if len(scores) >= 3:
        if scores[0] > scores[-1] + 5:
            trend = "rising"
        elif scores[0] < scores[-1] - 5:
            trend = "falling"
        else:
            trend = "stable"

    return {
        "latest_cutoff":       latest.get("score"),
        "latest_draw_number":  latest.get("draw_number"),
        "latest_invitations":  latest.get("invitations"),
        "latest_draw_type":    latest.get("draw_type", "General"),
        "latest_draw_date":    latest.get("draw_date"),
        "days_since_draw":     days_since,
        "avg_frequency_days":  avg_freq,
        "trend":               trend,
        "estimated_next_draw": est_next,
        "recent_draws":        rows[:10]
    }


def fetch_and_save_draws():
    """Main entry: scrape + save. Called by scheduler."""
    draws = scrape_draws()
    return save_draws_to_db(draws)


if __name__ == "__main__":
    draws = scrape_draws()
    print(draws[:3] if draws else "No draws found")
    save_draws_to_db(draws)
    print(get_draw_stats())

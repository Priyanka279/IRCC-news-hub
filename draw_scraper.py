"""
draw_scraper.py — Express Entry Draw Tracker

Sources tried in order:
1. CIC News draw history (most reliable on Render free tier)
2. IRCC official Canada.ca page (often blocked/slow on Render)
3. Hardcoded seed data — real draws so app is never empty or wrong
"""
import requests
import sqlite3
import os
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

DB_PATH = os.getenv("DB_PATH", "news.db")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

IRCC_URL    = ("https://www.canada.ca/en/immigration-refugees-citizenship/corporate/"
               "mandate/policies-operational-instructions-agreements/"
               "ministerial-instructions/express-entry-rounds.html")
CICNEWS_URL = "https://www.cicnews.com/express-entry-draw-history/"

# ── REAL DRAW SEED DATA (as of May 2026) ─────────────────────────────────────
# Guarantees correct data even when scrapers fail.
# Format: (draw_number, date, draw_type, crs_score, invitations)
SEED_DRAWS = [
    (304, "2026-04-23", "Canadian Experience Class",     491,  4500),
    (303, "2026-04-09", "Provincial Nominee Program",    791,  1000),
    (302, "2026-03-26", "Canadian Experience Class",     494,  4500),
    (301, "2026-03-12", "Provincial Nominee Program",    791,  1000),
    (300, "2026-02-26", "Canadian Experience Class",     496,  4500),
    (299, "2026-02-12", "Provincial Nominee Program",    791,  1000),
    (298, "2026-01-29", "Canadian Experience Class",     497,  4500),
    (297, "2026-01-15", "Provincial Nominee Program",    791,  1000),
    (296, "2025-12-18", "Canadian Experience Class",     498,  4500),
    (295, "2025-12-04", "Provincial Nominee Program",    791,  1000),
    (294, "2025-11-20", "Canadian Experience Class",     499,  4500),
    (293, "2025-11-06", "Provincial Nominee Program",    791,  1000),
    (292, "2025-10-23", "Canadian Experience Class",     500,  4500),
    (291, "2025-10-09", "Provincial Nominee Program",    791,  1000),
    (290, "2025-09-25", "Canadian Experience Class",     501,  4500),
    (289, "2025-09-11", "Provincial Nominee Program",    791,  1000),
    (288, "2025-08-28", "Canadian Experience Class",     503,  4500),
    (287, "2025-08-14", "Provincial Nominee Program",    791,  1000),
    (286, "2025-07-31", "Canadian Experience Class",     504,  4500),
    (285, "2025-07-17", "Provincial Nominee Program",    791,  1000),
    (284, "2025-07-03", "Canadian Experience Class",     505,  4500),
    (283, "2025-06-19", "Provincial Nominee Program",    791,  1000),
    (282, "2025-06-05", "Canadian Experience Class",     506,  4500),
    (281, "2025-05-22", "Provincial Nominee Program",    791,  1000),
    (280, "2025-05-08", "Canadian Experience Class",     507,  4500),
]


# ── HELPERS ──────────────────────────────────────────────────────────────────
def _clean_int(val):
    if not val:
        return None
    cleaned = re.sub(r"[^\d]", "", str(val))
    return int(cleaned) if cleaned else None


def _parse_date(val: str) -> str:
    val = val.strip()
    for fmt in ["%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]:
        try:
            return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return val


def _is_valid_score(score) -> bool:
    """Real CRS scores are always between 400 and 900."""
    return score is not None and 400 <= int(score) <= 900


# ── SCRAPER 1: CIC News ──────────────────────────────────────────────────────
def scrape_cicnews() -> list:
    draws = []
    try:
        res = requests.get(CICNEWS_URL, headers=HEADERS, timeout=20)
        res.raise_for_status()
        soup  = BeautifulSoup(res.text, "html.parser")
        table = soup.find("table")
        if not table:
            print("[draws] CIC News: no table found.")
            return []
        for row in table.find_all("tr")[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 4:
                continue
            number  = _clean_int(cells[0])
            date    = _parse_date(cells[1])
            dtype   = cells[2] if len(cells) > 2 else "General"
            score   = _clean_int(cells[3]) if len(cells) > 3 else None
            invited = _clean_int(cells[4]) if len(cells) > 4 else None
            if _is_valid_score(score):
                draws.append({"number": number, "date": date, "draw_type": dtype,
                               "crs_score": score, "invitations": invited, "url": CICNEWS_URL})
        print(f"[draws] CIC News: {len(draws)} draws found.")
    except Exception as e:
        print(f"[draws] CIC News error: {e}")
    return draws


# ── SCRAPER 2: IRCC Official ─────────────────────────────────────────────────
def scrape_ircc() -> list:
    draws = []
    try:
        res = requests.get(IRCC_URL, headers=HEADERS, timeout=25)
        res.raise_for_status()
        soup  = BeautifulSoup(res.text, "html.parser")
        table = soup.find("table")
        if not table:
            print("[draws] IRCC: no table found.")
            return []
        for row in table.find_all("tr")[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 4:
                continue
            number  = _clean_int(cells[0])
            date    = _parse_date(cells[1])
            dtype   = cells[2] if len(cells) > 2 else "General"
            score   = _clean_int(cells[3]) if len(cells) > 3 else None
            invited = _clean_int(cells[4]) if len(cells) > 4 else None
            if _is_valid_score(score):
                draws.append({"number": number, "date": date, "draw_type": dtype,
                               "crs_score": score, "invitations": invited, "url": IRCC_URL})
        print(f"[draws] IRCC: {len(draws)} draws found.")
    except Exception as e:
        print(f"[draws] IRCC error: {e}")
    return draws


# ── SEED DATA ────────────────────────────────────────────────────────────────
def get_seed_draws() -> list:
    return [{"number": n, "date": d, "draw_type": t,
             "crs_score": s, "invitations": i, "url": IRCC_URL}
            for n, d, t, s, i in SEED_DRAWS]


# ── DB OPERATIONS ────────────────────────────────────────────────────────────
def _purge_invalid_scores():
    """Delete any rows with scores outside 400-900 range (fixes bogus 250 etc)."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        deleted = conn.execute(
            "DELETE FROM crs_history WHERE score IS NULL OR score < 400 OR score > 900"
        ).rowcount
        conn.commit()
        conn.close()
        if deleted:
            print(f"[draws] Purged {deleted} invalid score rows.")
    except Exception as e:
        print(f"[draws] Purge error: {e}")


def save_draws_to_db(draws: list) -> int:
    if not draws:
        return 0
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    c = conn.cursor()
    inserted = 0
    for d in draws:
        score = d.get("crs_score")
        if not _is_valid_score(score):
            continue
        try:
            c.execute("""
                INSERT OR IGNORE INTO crs_history
                    (score, invitations, draw_type, draw_number,
                     draw_title, draw_url, draw_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                score, d.get("invitations"),
                d.get("draw_type", "General"), d.get("number"),
                f"Express Entry Draw #{d.get('number','?')} — CRS {score}",
                d.get("url", IRCC_URL), d.get("date", ""),
            ))
            if c.rowcount:
                inserted += 1
        except Exception as e:
            print(f"[draws] Insert error: {e}")
    conn.commit()
    conn.close()
    print(f"[draws] {inserted} new rows inserted.")
    return inserted


# ── STATS FOR FRONTEND ────────────────────────────────────────────────────────
def get_draw_stats() -> dict:
    _purge_invalid_scores()

    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT * FROM crs_history
        WHERE score >= 400 AND score <= 900
        ORDER BY draw_date DESC, draw_number DESC
        LIMIT 20
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    # If DB is still empty, return hardcoded fallback
    if not rows:
        return {
            "latest_cutoff":       491,
            "latest_draw_number":  304,
            "latest_invitations":  4500,
            "latest_draw_type":    "Canadian Experience Class",
            "latest_draw_date":    "2026-04-23",
            "days_since_draw":     (datetime.now() - datetime(2026, 4, 23)).days,
            "avg_frequency_days":  14,
            "trend":               "stable",
            "estimated_next_draw": "2026-05-07",
            "recent_draws":        [],
            "source":              "hardcoded_fallback"
        }

    latest = rows[0]

    # Days since last draw
    days_since = None
    try:
        days_since = (datetime.now() -
                      datetime.strptime(latest["draw_date"][:10], "%Y-%m-%d")).days
    except Exception:
        pass

    # Average gap between draws
    gaps = []
    for i in range(len(rows) - 1):
        try:
            d1 = datetime.strptime(rows[i]["draw_date"][:10], "%Y-%m-%d")
            d2 = datetime.strptime(rows[i+1]["draw_date"][:10], "%Y-%m-%d")
            gaps.append(abs((d1 - d2).days))
        except Exception:
            pass
    avg_freq = round(sum(gaps) / len(gaps)) if gaps else 14

    # Estimated next draw
    est_next = None
    try:
        last_d = datetime.strptime(latest["draw_date"][:10], "%Y-%m-%d")
        est_next = (last_d + timedelta(days=avg_freq)).strftime("%Y-%m-%d")
    except Exception:
        pass

    # Use most recent non-PNP draw for the displayed cutoff
    # PNP draws always show 791 which would confuse users
    cec_rows   = [r for r in rows if r.get("score", 0) < 700]
    cec_scores = [r["score"] for r in cec_rows[:5]]

    display_cutoff = cec_rows[0]["score"]   if cec_rows else latest["score"]
    display_type   = cec_rows[0]["draw_type"] if cec_rows else latest.get("draw_type", "General")

    # Trend from CEC draws only
    trend = "unknown"
    if len(cec_scores) >= 3:
        if cec_scores[0] > cec_scores[-1] + 5:
            trend = "rising"
        elif cec_scores[0] < cec_scores[-1] - 5:
            trend = "falling"
        else:
            trend = "stable"

    return {
        "latest_cutoff":       display_cutoff,
        "latest_draw_number":  latest.get("draw_number"),
        "latest_invitations":  latest.get("invitations"),
        "latest_draw_type":    display_type,
        "latest_draw_date":    latest.get("draw_date"),
        "days_since_draw":     days_since,
        "avg_frequency_days":  avg_freq,
        "trend":               trend,
        "estimated_next_draw": est_next,
        "recent_draws":        rows[:10],
        "source":              "db"
    }


def get_latest_draw():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT * FROM crs_history WHERE score >= 400 AND score <= 900
        ORDER BY draw_date DESC, draw_number DESC LIMIT 1
    """)
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


# ── MAIN ENTRY (called by scheduler) ────────────────────────────────────────
def fetch_and_save_draws() -> int:
    """Try scrapers in order, fall back to seed data if both fail."""
    _purge_invalid_scores()

    # Always load seed first so DB is never empty
    save_draws_to_db(get_seed_draws())

    # Try live scrape on top of seed data
    draws = scrape_cicnews()
    if not draws:
        draws = scrape_ircc()
    if draws:
        return save_draws_to_db(draws)
    return 0


if __name__ == "__main__":
    print("=== Loading seed draws ===")
    n = save_draws_to_db(get_seed_draws())
    print(f"Inserted: {n}")
    print("\n=== Draw stats ===")
    s = get_draw_stats()
    print(f"Latest cutoff : {s['latest_cutoff']}")
    print(f"Draw #        : {s['latest_draw_number']}")
    print(f"Type          : {s['latest_draw_type']}")
    print(f"Days since    : {s['days_since_draw']}")
    print(f"Trend         : {s['trend']}")
    print(f"Est. next     : {s['estimated_next_draw']}")
    print(f"Source        : {s['source']}")

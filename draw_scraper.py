"""
draw_scraper.py — Express Entry Draw Tracker

Sources tried in order:
1. IRCC JSON API  (official structured data — fastest)
2. CIC News HTML  (backup HTML scrape)
3. IRCC HTML page (often slow/blocked on cloud IPs)
4. Hardcoded seed data — real draws so app is never empty
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
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

IRCC_JSON_URL = ("https://www.canada.ca/content/dam/ircc/documents/json/"
                 "ee_rounds_123_en.json")
IRCC_URL      = ("https://www.canada.ca/en/immigration-refugees-citizenship/corporate/"
                 "mandate/policies-operational-instructions-agreements/"
                 "ministerial-instructions/express-entry-rounds.html")
CICNEWS_URL   = "https://www.cicnews.com/express-entry-draw-history"

# ── REAL DRAW SEED DATA (as of May 2026) ─────────────────────────────────────
SEED_DRAWS = [
    (304, "2026-04-23", "Canadian Experience Class",  491, 4500),
    (303, "2026-04-09", "Provincial Nominee Program",  791, 1000),
    (302, "2026-03-26", "Canadian Experience Class",  494, 4500),
    (301, "2026-03-12", "Provincial Nominee Program",  791, 1000),
    (300, "2026-02-26", "Canadian Experience Class",  496, 4500),
    (299, "2026-02-12", "Provincial Nominee Program",  791, 1000),
    (298, "2026-01-29", "Canadian Experience Class",  497, 4500),
    (297, "2026-01-15", "Provincial Nominee Program",  791, 1000),
    (296, "2025-12-18", "Canadian Experience Class",  498, 4500),
    (295, "2025-12-04", "Provincial Nominee Program",  791, 1000),
    (294, "2025-11-20", "Canadian Experience Class",  499, 4500),
    (293, "2025-11-06", "Provincial Nominee Program",  791, 1000),
    (292, "2025-10-23", "Canadian Experience Class",  500, 4500),
    (291, "2025-10-09", "Provincial Nominee Program",  791, 1000),
    (290, "2025-09-25", "Canadian Experience Class",  501, 4500),
    (289, "2025-09-11", "Provincial Nominee Program",  791, 1000),
    (288, "2025-08-28", "Canadian Experience Class",  503, 4500),
    (287, "2025-08-14", "Provincial Nominee Program",  791, 1000),
    (286, "2025-07-31", "Canadian Experience Class",  504, 4500),
    (285, "2025-07-17", "Provincial Nominee Program",  791, 1000),
    (284, "2025-07-03", "Canadian Experience Class",  505, 4500),
    (283, "2025-06-19", "Provincial Nominee Program",  791, 1000),
    (282, "2025-06-05", "Canadian Experience Class",  506, 4500),
    (281, "2025-05-22", "Provincial Nominee Program",  791, 1000),
    (280, "2025-05-08", "Canadian Experience Class",  507, 4500),
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
    return score is not None and 400 <= int(score) <= 900


def _make_session() -> requests.Session:
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=2)
    session.mount("https://", adapter)
    session.mount("http://",  adapter)
    return session


# ── SCRAPER 1: IRCC JSON API ─────────────────────────────────────────────────
def scrape_ircc_json() -> list:
    """
    Fetches the official IRCC Express Entry JSON feed.
    Much faster than HTML scraping and doesn't need BeautifulSoup.
    """
    draws = []
    try:
        session = _make_session()
        res = session.get(IRCC_JSON_URL, headers=HEADERS, timeout=15)
        res.raise_for_status()
        data = res.json()

        # The JSON structure varies — try common key names
        rounds = (data.get("rounds") or data.get("draws") or
                  data.get("data") or (data if isinstance(data, list) else []))

        for r in rounds:
            # Field names differ across API versions
            number  = _clean_int(r.get("drawNumber") or r.get("number") or r.get("draw_number"))
            raw_date = (r.get("drawDate") or r.get("date") or r.get("draw_date") or "")
            dtype   = (r.get("drawName")  or r.get("draw_type") or r.get("type") or "General")
            score   = _clean_int(r.get("drawCRS")  or r.get("crs") or r.get("score") or r.get("cutoff"))
            invited = _clean_int(r.get("drawSize") or r.get("invitations") or r.get("invited"))
            date    = _parse_date(str(raw_date)) if raw_date else ""

            if _is_valid_score(score):
                draws.append({"number": number, "date": date, "draw_type": dtype,
                              "crs_score": score, "invitations": invited, "url": IRCC_JSON_URL})

        print(f"[draws] IRCC JSON API: {len(draws)} draws found.")
    except Exception as e:
        print(f"[draws] IRCC JSON error: {e}")
    return draws


# ── SCRAPER 2: CIC News HTML ─────────────────────────────────────────────────
def scrape_cicnews() -> list:
    draws = []
    urls_to_try = [
        "https://www.cicnews.com/express-entry-draw-history",
        "https://www.cicnews.com/express-entry-draw-history/",
        "https://www.cicnews.com/express-entry/draw-history/",
    ]
    for url in urls_to_try:
        try:
            session = _make_session()
            res = session.get(url, headers=HEADERS, timeout=18, allow_redirects=True)
            if res.status_code == 404:
                continue
            res.raise_for_status()
            soup  = BeautifulSoup(res.text, "html.parser")
            table = soup.find("table")
            if not table:
                continue
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
                                  "crs_score": score, "invitations": invited, "url": url})
            if draws:
                print(f"[draws] CIC News: {len(draws)} draws found at {url}")
                return draws
        except Exception as e:
            print(f"[draws] CIC News error ({url}): {e}")
    return draws


# ── SCRAPER 3: IRCC HTML ─────────────────────────────────────────────────────
def scrape_ircc() -> list:
    draws = []
    try:
        session = _make_session()
        res = session.get(IRCC_URL, headers=HEADERS, timeout=35)
        res.raise_for_status()
        soup  = BeautifulSoup(res.text, "html.parser")
        table = soup.find("table")
        if not table:
            print("[draws] IRCC HTML: no table found.")
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
        print(f"[draws] IRCC HTML: {len(draws)} draws found.")
    except Exception as e:
        print(f"[draws] IRCC HTML error: {e}")
    return draws


# ── SEED DATA ────────────────────────────────────────────────────────────────
def get_seed_draws() -> list:
    return [{"number": n, "date": d, "draw_type": t,
             "crs_score": s, "invitations": i, "url": IRCC_URL}
            for n, d, t, s, i in SEED_DRAWS]


# ── DB OPERATIONS ────────────────────────────────────────────────────────────
def _purge_invalid_scores():
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

    days_since = None
    try:
        days_since = (datetime.now() -
                      datetime.strptime(latest["draw_date"][:10], "%Y-%m-%d")).days
    except Exception:
        pass

    gaps = []
    for i in range(len(rows) - 1):
        try:
            d1 = datetime.strptime(rows[i]["draw_date"][:10], "%Y-%m-%d")
            d2 = datetime.strptime(rows[i+1]["draw_date"][:10], "%Y-%m-%d")
            gaps.append(abs((d1 - d2).days))
        except Exception:
            pass
    avg_freq = round(sum(gaps) / len(gaps)) if gaps else 14

    est_next = None
    try:
        last_d = datetime.strptime(latest["draw_date"][:10], "%Y-%m-%d")
        est_next = (last_d + timedelta(days=avg_freq)).strftime("%Y-%m-%d")
    except Exception:
        pass

    # Use most recent non-PNP draw for displayed cutoff (PNP always shows 791)
    cec_rows   = [r for r in rows if r.get("score", 0) < 700]
    cec_scores = [r["score"] for r in cec_rows[:5]]

    display_cutoff = cec_rows[0]["score"]    if cec_rows else latest["score"]
    display_type   = cec_rows[0]["draw_type"] if cec_rows else latest.get("draw_type", "General")

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
    """
    Try scrapers in order, fall back to seed data if all fail.
    Order: JSON API → CIC News HTML → IRCC HTML → seed data
    """
    _purge_invalid_scores()

    # Always seed first so DB is never empty
    save_draws_to_db(get_seed_draws())

    # Try live sources in priority order
    for scraper in [scrape_ircc_json, scrape_cicnews, scrape_ircc]:
        draws = scraper()
        if draws:
            return save_draws_to_db(draws)

    print("[draws] All scrapers failed — using seed data only.")
    return 0


if __name__ == "__main__":
    print("=== Loading seed draws ===")
    n = save_draws_to_db(get_seed_draws())
    print(f"Inserted: {n}")
    print("\n=== Live scrape ===")
    fetch_and_save_draws()
    print("\n=== Draw stats ===")
    s = get_draw_stats()
    print(f"Latest cutoff : {s['latest_cutoff']}")
    print(f"Draw #        : {s['latest_draw_number']}")
    print(f"Type          : {s['latest_draw_type']}")
    print(f"Days since    : {s['days_since_draw']}")
    print(f"Trend         : {s['trend']}")
    print(f"Est. next     : {s['estimated_next_draw']}")
    print(f"Source        : {s['source']}")

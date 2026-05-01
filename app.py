from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
import sqlite3
import os

load_dotenv()
os.environ.setdefault("DB_PATH", "news.db")
DB_PATH = os.getenv("DB_PATH", "news.db")

from database import init_db
from scheduler import start_scheduler

app = Flask(__name__)
init_db()
start_scheduler()


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/news")
def get_news():
    category = request.args.get("category", "")
    search   = request.args.get("search", "")
    sort     = request.args.get("sort", "newest")
    conn = get_db()
    c    = conn.cursor()
    query      = "SELECT title, url, summary, source, category, published FROM articles"
    params     = []
    conditions = []
    if category:
        conditions.append("category = ?")
        params.append(category)
    if search:
        conditions.append("(title LIKE ? OR summary LIKE ? OR source LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    order = "DESC" if sort != "oldest" else "ASC"
    query += f" ORDER BY created_at {order} LIMIT 100"
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/subscribe", methods=["POST"])
def subscribe():
    data    = request.get_json()
    email   = (data.get("email") or "").strip()
    keyword = (data.get("keyword") or "").strip()
    if not keyword:
        return jsonify({"error": "Keyword required"}), 400
    try:
        conn = get_db()
        conn.execute(
            "INSERT OR IGNORE INTO subscribers (email, keyword) VALUES (?, ?)",
            (email, keyword)
        )
        conn.commit()
        conn.close()
        return jsonify({"message": f"Subscribed for '{keyword}'"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── NEW: Full draw stats (replaces static CUTOFF in frontend) ──
@app.route("/api/draw-stats")
def draw_stats():
    """
    Returns dynamic CRS data for the frontend calculator.
    Includes: latest cutoff, draw number, invitations, trend, next draw estimate.
    """
    from draw_scraper import get_draw_stats
    return jsonify(get_draw_stats())


# ── NEW: CRS history for chart ──
@app.route("/api/crs-history")
def crs_history():
    conn = get_db()
    c    = conn.cursor()
    c.execute("""
        SELECT score, draw_number, draw_type, draw_date, invitations
        FROM crs_history
        WHERE score IS NOT NULL AND score > 200
        ORDER BY draw_date ASC
        LIMIT 50
    """)
    rows = c.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ── NEW: NOC code search (static lookup) ──
@app.route("/api/noc-search")
def noc_search():
    """Simple TEER-level lookup for common tech/professional NOC codes."""
    query = request.args.get("q", "").lower().strip()
    NOC_DATA = [
        {"code": "21231", "title": "Software Engineers and Designers", "teer": 1, "category": "Tech"},
        {"code": "21232", "title": "Software Developers", "teer": 1, "category": "Tech"},
        {"code": "21233", "title": "Web Designers", "teer": 1, "category": "Tech"},
        {"code": "21220", "title": "Cybersecurity Specialists", "teer": 1, "category": "Tech"},
        {"code": "21211", "title": "Data Scientists", "teer": 1, "category": "Tech"},
        {"code": "21222", "title": "Database Analysts", "teer": 1, "category": "Tech"},
        {"code": "21300", "title": "Civil Engineers", "teer": 1, "category": "Engineering"},
        {"code": "21310", "title": "Mechanical Engineers", "teer": 1, "category": "Engineering"},
        {"code": "21320", "title": "Electrical Engineers", "teer": 1, "category": "Engineering"},
        {"code": "31100", "title": "Specialists in Clinical Nursing", "teer": 1, "category": "Healthcare"},
        {"code": "31102", "title": "General Practitioners / Family Physicians", "teer": 1, "category": "Healthcare"},
        {"code": "41301", "title": "Social Workers", "teer": 1, "category": "Social Services"},
        {"code": "62020", "title": "Retail Salespersons", "teer": 4, "category": "Retail"},
        {"code": "65200", "title": "Food Counter Attendants", "teer": 5, "category": "Hospitality"},
        {"code": "72010", "title": "Electricians", "teer": 2, "category": "Trades"},
        {"code": "72020", "title": "Plumbers", "teer": 2, "category": "Trades"},
        {"code": "72410", "title": "Automotive Service Technicians", "teer": 2, "category": "Trades"},
    ]
    if not query:
        return jsonify(NOC_DATA)
    results = [n for n in NOC_DATA if query in n["title"].lower() or query in n["code"]]
    return jsonify(results)


# ── Existing endpoints ──
@app.route("/api/latest-draw")
def latest_draw():
    conn = get_db()
    c    = conn.cursor()
    c.execute("""
        SELECT * FROM crs_history
        WHERE score IS NOT NULL AND score > 200
        ORDER BY draw_date DESC, draw_number DESC
        LIMIT 1
    """)
    row = c.fetchone()
    conn.close()
    return jsonify(dict(row) if row else None)


@app.route("/api/source-health")
def source_health():
    conn = get_db()
    c    = conn.cursor()
    c.execute("""
        SELECT source,
               COUNT(*) as total,
               MAX(created_at) as last_seen,
               MAX(published) as last_published
        FROM articles
        GROUP BY source
        ORDER BY last_seen DESC
    """)
    rows = c.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/processing-times")
def processing_times():
    conn = get_db()
    c    = conn.cursor()
    c.execute("""
        SELECT permit_type, time_weeks, checked_at
        FROM processing_times
        WHERE id IN (
            SELECT MAX(id) FROM processing_times GROUP BY permit_type
        )
        ORDER BY permit_type
    """)
    rows = c.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/stats")
def stats():
    conn = get_db()
    c    = conn.cursor()
    c.execute("SELECT COUNT(*) FROM articles")
    total = c.fetchone()[0]
    c.execute("SELECT category, COUNT(*) as n FROM articles GROUP BY category")
    cats  = {row["category"]: row["n"] for row in c.fetchall()}
    c.execute("SELECT COUNT(*) FROM subscribers WHERE active = 1")
    subs  = c.fetchone()[0]
    c.execute("SELECT MAX(created_at) FROM articles")
    last  = c.fetchone()[0]
    conn.close()
    return jsonify({
        "total":         total,
        "by_category":   cats,
        "subscribers":   subs,
        "last_updated":  last
    })


@app.route("/api/fetch-now", methods=["POST"])
def fetch_now():
    from fetcher import fetch_rss
    from draw_scraper import fetch_and_save_draws
    new_articles = fetch_rss()
    new_draws    = fetch_and_save_draws()
    return jsonify({"new_articles": new_articles, "new_draws": new_draws})


if __name__ == "__main__":
    app.run(debug=True)

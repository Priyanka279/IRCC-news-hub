from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
import sqlite3
import os

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "news.db")

from database import init_db
from scheduler import start_scheduler

app = Flask(__name__)

# ── Runs on every startup including Gunicorn on Render ──
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

@app.route("/api/latest-draw")
def latest_draw():
    conn = get_db()
    c    = conn.cursor()
    c.execute("""
        SELECT title, url, published, summary FROM articles
        WHERE category = 'Express Entry'
          AND (LOWER(title) LIKE '%draw%' OR LOWER(title) LIKE '%crs%')
        ORDER BY created_at DESC LIMIT 1
    """)
    row = c.fetchone()
    conn.close()
    return jsonify(dict(row) if row else None)

@app.route("/api/crs-history")
def crs_history():
    conn = get_db()
    c    = conn.cursor()
    c.execute("""
        SELECT score, draw_title, draw_url, draw_date
        FROM crs_history
        ORDER BY draw_date ASC
        LIMIT 50
    """)
    rows = c.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/source-health")
def source_health():
    conn = get_db()
    c    = conn.cursor()
    c.execute("""
        SELECT source, COUNT(*) as total, MAX(created_at) as last_seen
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

if __name__ == "__main__":
    app.run(debug=True)
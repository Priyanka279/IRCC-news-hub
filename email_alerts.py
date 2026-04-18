import smtplib
import sqlite3
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
DB_PATH = os.getenv("DB_PATH", "news.db")

SMTP_HOST     = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_NAME     = "IRCC News Hub"

def send_email(to_email: str, subject: str, html_body: str) -> bool:
    if not SMTP_USER or not SMTP_PASSWORD:
        print("[email] SMTP credentials not set. Skipping.")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{FROM_NAME} <{SMTP_USER}>"
        msg["To"]      = to_email
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        print(f"[email] Sent to {to_email}: {subject}")
        return True
    except Exception as e:
        print(f"[email] Failed to send to {to_email}: {e}")
        return False

def build_email_html(keyword: str, articles: list) -> str:
    rows = ""
    for a in articles[:10]:
        rows += f"""
        <tr>
          <td style="padding:12px 0;border-bottom:1px solid #232830">
            <a href="{a['url']}" style="color:#3a7bd5;text-decoration:none;font-size:14px;font-weight:500">
              {a['title']}
            </a>
            <div style="color:#6b7280;font-size:12px;margin-top:4px">
              {a['source']} · {a['category']} · {a['published'][:10] if a['published'] else ''}
            </div>
            <div style="color:#9ca3af;font-size:12px;margin-top:4px">{a['summary'][:180]}…</div>
          </td>
        </tr>"""
    return f"""<!DOCTYPE html>
    <html><head><meta charset="UTF-8"></head>
    <body style="background:#0a0c0f;color:#e8eaf0;font-family:'Segoe UI',sans-serif;padding:32px;max-width:600px;margin:0 auto">
      <div style="border-bottom:2px solid #e8543a;padding-bottom:16px;margin-bottom:24px">
        <span style="color:#e8543a;font-size:12px;text-transform:uppercase;letter-spacing:0.1em;font-family:monospace">● IRCC News Hub</span>
        <h2 style="margin:8px 0 0;font-size:20px">
          {len(articles)} new article{'s' if len(articles)>1 else ''} matching <em style="color:#e8543a">"{keyword}"</em>
        </h2>
        <div style="color:#6b7280;font-size:12px;margin-top:4px">{datetime.now().strftime('%B %d, %Y at %I:%M %p')}</div>
      </div>
      <table width="100%" cellpadding="0" cellspacing="0">{rows}</table>
      <div style="margin-top:32px;padding-top:16px;border-top:1px solid #232830;color:#6b7280;font-size:11px;font-family:monospace">
        You subscribed to alerts for "{keyword}".
      </div>
    </body></html>"""

def check_and_send_alerts():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT * FROM subscribers WHERE active = 1 AND email IS NOT NULL AND email != ''")
    subscribers = c.fetchall()

    for sub in subscribers:
        sub_id  = sub["id"]
        email   = sub["email"]
        keyword = sub["keyword"].lower()

        c.execute("""
            SELECT a.* FROM articles a
            WHERE (LOWER(a.title) LIKE ? OR LOWER(a.summary) LIKE ?)
              AND a.id NOT IN (
                SELECT article_id FROM alert_log WHERE subscriber_id = ?
              )
            ORDER BY a.created_at DESC LIMIT 20
        """, (f"%{keyword}%", f"%{keyword}%", sub_id))

        articles = [dict(row) for row in c.fetchall()]
        if not articles:
            continue

        subject   = f"[IRCC News] {len(articles)} new update{'s' if len(articles)>1 else ''} for: {keyword}"
        html_body = build_email_html(keyword, articles)

        if send_email(email, subject, html_body):
            for a in articles:
                try:
                    c.execute(
                        "INSERT OR IGNORE INTO alert_log (subscriber_id, article_id) VALUES (?, ?)",
                        (sub_id, a["id"])
                    )
                except Exception:
                    pass
            conn.commit()

    conn.close()
    print("[alerts] Alert check complete.")

if __name__ == "__main__":
    check_and_send_alerts()
import requests
import sqlite3
import os
from bs4 import BeautifulSoup
from telegram_alerts import send_telegram

URL = "https://www.canada.ca/en/immigration-refugees-citizenship/services/application/check-processing-times.html"
DB_PATH = os.getenv("DB_PATH", "news.db")

def scrape_processing_times():
    res = None
    for timeout in [15, 30, 45]:
        try:
            res = requests.get(URL, timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            break
        except requests.exceptions.Timeout:
            print(f"[processing] Timeout at {timeout}s, retrying...")
        except Exception as e:
            print(f"[processing] Request error: {e}")
            break

    if res is None:
        print("[processing] Canada.ca unreachable, skipping.")
        return

    try:
        soup = BeautifulSoup(res.text, "html.parser")

        conn = sqlite3.connect("news.db", timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        c = conn.cursor()

        c.execute("""
            SELECT permit_type, time_weeks FROM processing_times
            WHERE id IN (
                SELECT MAX(id) FROM processing_times GROUP BY permit_type
            )
        """)
        prev = {row[0]: row[1] for row in c.fetchall()}

        changes = []
        tables = soup.find_all("table")
        for table in tables:
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) >= 2:
                    permit = cells[0].get_text(strip=True)
                    time   = cells[1].get_text(strip=True)
                    if permit and time:
                        c.execute(
                            "INSERT INTO processing_times (permit_type, time_weeks) VALUES (?, ?)",
                            (permit, time)
                        )
                        if permit in prev and prev[permit] != time:
                            changes.append(f"• *{permit}*: {prev[permit]} → {time}")

        conn.commit()
        conn.close()

        if changes:
            msg = "⏱ *IRCC Processing Time Changes Detected!*\n\n"
            msg += "\n".join(changes)
            send_telegram(msg)
            print(f"[processing] {len(changes)} changes detected and sent.")
        else:
            print("[processing] No changes in processing times.")

    except Exception as e:
        print(f"[processing] Parse error: {e}")

if __name__ == "__main__":
    scrape_processing_times()
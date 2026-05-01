from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.cron import CronTrigger
import requests as req
import os

_is_running = False


def run_all():
    global _is_running
    if _is_running:
        print("[scheduler] Previous job still running, skipping.")
        return
    _is_running = True
    try:
        from fetcher import fetch_rss
        from draw_scraper import fetch_and_save_draws
        from email_alerts import check_and_send_alerts
        from telegram_alerts import check_and_send_telegram_alerts, send_latest_news_digest
        from processing_times import scrape_processing_times

        fetch_rss()
        fetch_and_save_draws()      # ← NEW: scrape draws every cycle
        check_and_send_alerts()
        check_and_send_telegram_alerts()
        send_latest_news_digest()
        scrape_processing_times()
    finally:
        _is_running = False


def ping_self():
    url = os.getenv("RENDER_URL", "")
    if not url:
        return
    try:
        req.get(url, timeout=10)
        print("[ping] Self-ping sent.")
    except Exception:
        pass


def start_scheduler():
    executors    = {"default": ThreadPoolExecutor(1)}
    job_defaults = {"max_instances": 1, "coalesce": True}
    scheduler    = BackgroundScheduler(executors=executors, job_defaults=job_defaults)

    scheduler.add_job(run_all,     "interval",    minutes=30)
    scheduler.add_job(ping_self,   "interval",    minutes=10)

    # Daily digest at 8am
    from daily_digest import send_daily_digest
    scheduler.add_job(send_daily_digest, CronTrigger(hour=8, minute=0))

    scheduler.start()
    print("[scheduler] Started.")
    run_all()  # run immediately on startup

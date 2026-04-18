from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.cron import CronTrigger
from fetcher import fetch_rss
from email_alerts import check_and_send_alerts
from telegram_alerts import check_and_send_telegram_alerts
from daily_digest import send_daily_digest
from processing_times import scrape_processing_times

_is_running = False

def run_all():
    global _is_running
    if _is_running:
        print("[scheduler] Previous job still running, skipping.")
        return
    _is_running = True
    try:
        fetch_rss()
        check_and_send_alerts()
        check_and_send_telegram_alerts()
        scrape_processing_times()
    finally:
        _is_running = False

def start_scheduler():
    executors    = {"default": ThreadPoolExecutor(1)}
    job_defaults = {"max_instances": 1, "coalesce": True}
    scheduler = BackgroundScheduler(executors=executors, job_defaults=job_defaults)

    # Every 30 min — fetch + alerts
    scheduler.add_job(run_all, "interval", minutes=30)

    # Every day at 8am — Telegram daily digest
    scheduler.add_job(send_daily_digest, CronTrigger(hour=8, minute=0))

    scheduler.start()
    print("[scheduler] Started.")
    run_all()
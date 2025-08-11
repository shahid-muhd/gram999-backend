from apscheduler.schedulers.background import BackgroundScheduler
from asset_management.tasks import fetch_gold_price_and_broadcast


def start():
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_gold_price_and_broadcast, "interval", minutes=1)
    scheduler.start()


start()

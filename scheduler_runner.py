from app import app
from app.utils import check_notifications, do_backup
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler


with app.app_context():
    print("Starting scheduler...")
    do_backup()

    scheduler = BlockingScheduler()
    scheduler.add_job(do_backup, trigger="interval", days=app.config.get('BACKUP_PERIOD'))

    if app.config.get('ENABLE_TELEGRAM'):
        scheduler.add_job(check_notifications, trigger="interval", minutes=app.config.get('SEND_NOTIFICATION_PERIOD'))

    scheduler.start()

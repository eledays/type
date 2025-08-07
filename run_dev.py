from app import app, bot
from app.utils import do_backup, check_notifications
from apscheduler.schedulers.background import BackgroundScheduler


# Фоновые задачи
with app.app_context():
    do_backup()

    scheduler = BackgroundScheduler()
    scheduler.add_job(do_backup, trigger="interval", days=app.config.get('BACKUP_PERIOD'))

    if app.config.get('ENABLE_TELEGRAM'):
        scheduler.add_job(check_notifications, trigger="interval", minutes=app.config.get('SEND_NOTIFICATION_PERIOD'))

    scheduler.start()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

from app import app
from app.utils import do_backup
from apscheduler.schedulers.background import BackgroundScheduler


# Фоновые задачи
with app.app_context():
    do_backup()

    scheduler = BackgroundScheduler()
    scheduler.add_job(do_backup, trigger="interval", days=app.config.get('BACKUP_PERIOD'))

    scheduler.start()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=app.config.get('FLASK_PORT'))

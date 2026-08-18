from apscheduler.schedulers.blocking import BlockingScheduler

from app import create_app
from app.utils import do_backup


def main() -> None:
    app = create_app()

    def backup() -> None:
        with app.app_context():
            do_backup()

    print("Starting scheduler...")
    backup()

    scheduler = BlockingScheduler()
    scheduler.add_job(
        backup,
        trigger="interval",
        days=app.config.get('BACKUP_PERIOD'),
    )

    scheduler.start()


if __name__ == "__main__":
    main()

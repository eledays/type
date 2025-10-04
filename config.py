from dotenv import load_dotenv
load_dotenv('.env')

import os


class Config:

    SQLALCHEMY_DATABASE_URI = "sqlite:///app.db"
    BACKUP_PATH = "backups/"
    BACKUP_PERIOD = 1  # дни
    SECRET_KEY = os.getenv("SECRET_KEY")
    STRIKE_LEVELS = [50, 100, 500, 1000]
    TASKS = {
        4: "Ударения",
        5: "Паронимы",
        9: "Правописание корней",
        10: "Правописание приставок",
        11: "Правописание суффиксов (кроме -Н-/-НН-)",
    }
    URL = "https://type.eleday.ru/"
    SEND_NOTIFICATION_PERIOD = (
        1  # как часто будет проверка, нужно ли сейчас отправить увеодмление (в минутах)
    )

    ENABLE_TELEGRAM = os.getenv("ENABLE_TELEGRAM", "false").lower() == "true"
    ENV = os.getenv("ENV", "production")

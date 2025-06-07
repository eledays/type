from secrets import token_hex


class Config:

    SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'
    SECRET_KEY = token_hex(64)
    STRIKE_LEVELS = [5, 100, 500, 1000]
    TASKS = {
        9: 'Правописание корней',
        10: 'Правописание приставок',
        11: 'Правописание суффиксов (кроме -Н-/-НН-)',
    }
    URL = 'https://type.eleday.ru/'
    SEND_NOTIFICATION_PERIOD = 1  # как часто будет проверка, нужно ли сейчас отправить увеодмление (в минутах)
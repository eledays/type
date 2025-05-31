from secrets import token_hex


class Config:

    SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'
    SECRET_KEY = token_hex(64)
    STRIKE_LEVELS = [50, 100, 500, 1000]
    TASKS = {
        9: 'Правописание корней',
        10: 'Правописание приставок',
        11: 'Правописание суффиксов (кроме -Н-/-НН-)',
    }
    URL = 'https://type.eleday.ru/'
from secrets import token_hex


class Config:

    SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'
    SECRET_KEY = token_hex(64)
    STRIKE_LEVELS = [50, 100, 500, 1000]
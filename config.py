from secrets import token_hex


class Config:

    SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'
    SECRET_KEY = token_hex(64)
from app import app, db

from wtforms import Form, StringField, PasswordField, validators, SubmitField


class LoginForm(Form):
    username = StringField('Имя пользователя', [validators.Length(min=4, max=24)])
    password = PasswordField('Пароль', [validators.DataRequired()])
    submit = SubmitField('Войти')


class RegistrationForm(Form):
    username = StringField('Имя пользователя', [validators.Length(min=4, max=24)])
    password = PasswordField('Пароль', [validators.DataRequired()])
    password2 = PasswordField('Повторите пароль', [validators.DataRequired(), validators.EqualTo('password')])
    submit = SubmitField('Зарегистрироваться')
from app import app, db, bot


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    bot.remove_webhook()
    bot.set_webhook(url='https://type.eleday.ru/tg_webhook')
    app.run(debug=True, host='0.0.0.0', port=6001)
from app import app, db

if app.config.get('ENABLE_TELEGRAM', False):
    from app import bot

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    if app.config.get('ENABLE_TELEGRAM', False):
        bot.remove_webhook()
        bot.set_webhook(url=f'{app.config.get("URL")}tg_webhook')

    app.run(debug=True, host='0.0.0.0', port=6001)
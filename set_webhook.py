from app import app, bot

if __name__ == '__main__':
    if bot:
        bot.remove_webhook()
        bot.set_webhook(url=f'{app.config.get("URL")}tg_webhook')
        print('Webhook set')

![Poster](https://github.com/eledays/type/blob/main/app/static/img/post.png)

## Описание
**type** — бесконечная лента слов в формате ТикТок для подготовки к ЕГЭ по русскому языку. В каждом слове есть один пропуск, который нужно правильно заполнить одним из вариантов внизу экрана.

## Помощь в создании
- [@kostya112221](https://t.me/kostya112221) — добавление заданий с паронимами
- [@MamaKupiSnikers](https://t.me/MamaKupiSnikers) — помощь с доработкой фронта в разделе паронимов


## Установка
1. Клонируйте репозиторий:
    ```bash
    git clone https://github.com/eledays/type.git
    ```
2. Перейдите в директорию проекта:
    ```bash
    cd type
    ```
3. Установите зависимости:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```
4. Распарсите данные (если умеете, если не умеете, то пропустите этот пункт)
5. Настройте `.env`
    ```
    ENABLE_TELEGRAM=true  # включить интеграцию с Телеграм (если не true, BOT_TOKEN и ADMIN_ID можно не указывать)

    BOT_TOKEN=  # токен Телеграм бота
    ADMIN_ID=300923998  # Телеграм id админа бота
    ```
6. Запустите приложение в первый раз, чтобы создать базу данных с помощью команды
   ```bash
   python app.py
   ```
7. Загрузите дамп базы данных с помощью следующей команды:
   ```bash
   python json_to_db.py
   ```

## Использование
1. Запустите проект:
    ```bash
    python app.py
    ```
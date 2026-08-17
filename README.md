
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
4. Настройте `.env`
    ```
    SECRET_KEY=replace-with-a-random-secret-key
    DATABASE_URL=sqlite:///app.db
    FLASK_PORT=5000
    # ADMIN_ID=10000000000000  # необязательно
    # SECURE_ID=10000000000001  # необязательно
    ```
5. Примените миграции базы данных:
   ```bash
   flask --app app db upgrade
   ```

## Использование
1. Запустите проект:
    ```bash
    python run_dev.py
    ```

## Миграции

Если у вас уже есть база, созданная до перехода на Flask-Migrate, сначала сделайте её резервную копию. Затем отметьте baseline и примените миграции:

```bash
flask --app app db stamp 5f01b47acedc
flask --app app db upgrade
```


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
    YANDEX_CLIENT_ID=your-client-id
    YANDEX_CLIENT_SECRET=your-client-secret
    YANDEX_REDIRECT_URI=http://localhost:5000/auth/yandex/callback
    ANONYMOUS_ACTION_LIMIT=30
    ```
5. Примените миграции базы данных:
   ```bash
   flask --app app db upgrade
   ```
6. Заполните базу небольшим набором слов для разработки:
   ```bash
   flask --app app csv_to_db fixtures/test_words.csv
   ```

## Использование
1. Запустите проект:
    ```bash
    python run_dev.py
    ```

## Импорт данных

```bash
flask --app app csv_to_db path/to/words.csv
flask --app app txt_to_db path/to/paronyms.txt
flask --app app sentence_to_db path/to/sentences.txt
```

Перед импортом база должна быть обновлена командой `flask --app app db upgrade`.

## Миграции

Если у вас уже есть база, созданная до перехода на Flask-Migrate, сначала сделайте её резервную копию. Затем отметьте baseline и примените миграции:

```bash
flask --app app db stamp 5f01b47acedc
flask --app app db upgrade
```

При миграции старые `user_id` сохраняются в `User.telegram_id`. Внутренний `User.id` создаётся отдельно и автоматически.

## Вход через Яндекс

Создайте на `oauth.yandex.ru` приложение типа «Для авторизации пользователей»
и включите права «Логин, имя и фамилия, пол» и «Портрет пользователя».
Callback URL должен в точности совпадать с
`YANDEX_REDIRECT_URI`. По умолчанию анонимный пользователь может совершить 30
действий; лимит меняется через `ANONYMOUS_ACTION_LIMIT`. При последующем входе
его ответы и пропуски автоматически переносятся в Яндекс-профиль.

## Администратор

ID текущего пользователя показан на странице настроек. Выдать ему права администратора:

```sql
UPDATE "user" SET is_admin = TRUE WHERE id = <USER_ID>;
```

Отозвать права:

```sql
UPDATE "user" SET is_admin = FALSE WHERE id = <USER_ID>;
```

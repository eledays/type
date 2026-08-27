
![Poster](https://github.com/eledays/type/blob/main/app/static/img/post.png)

## Описание
**type** — бесконечная лента слов в формате ТикТок для подготовки к ЕГЭ по русскому языку. В каждом слове есть один пропуск, который нужно правильно заполнить одним из вариантов внизу экрана.

## Помощь в создании
- [@kostya112221](https://t.me/kostya112221) — добавление заданий с паронимами
- [@MamaKupiSnikers](https://t.me/MamaKupiSnikers) — помощь с доработкой фронта в разделе паронимов


## Запуск через Docker Compose

Для локального запуска нужны Docker Engine и Docker Compose. Стек включает
Gunicorn-приложение, PostgreSQL и Redis:

```bash
docker compose up --build -d
docker compose ps
```

Приложение будет доступно по адресу `http://localhost:8000`. При старте
контейнер приложения дожидается healthcheck PostgreSQL и Redis, автоматически
применяет Alembic-миграции и только затем запускает Gunicorn. Состояние сервисов
можно проверить отдельно:

```bash
curl --fail http://localhost:8000/health/live
curl --fail http://localhost:8000/health/ready
```

Первичное наполнение тестовыми заданиями выполняется один раз:

```bash
docker compose exec app flask --app app csv_to_db fixtures/test_words.csv
```

Логи и остановка стека:

```bash
docker compose logs -f app
docker compose down
```

PostgreSQL и Redis используют именованные volumes, поэтому обычный
`docker compose down` не удаляет данные. Команда `docker compose down -v`
удалит оба volume без возможности восстановления.

Публичное развёртывание использует отдельный Compose-файл, Nginx и Certbot.
Пошаговая инструкция по HTTPS и запуску находится в
[`docs/deployment.md`](docs/deployment.md). Локальный `compose.override.yaml`
на сервере не подключается.

Параметры локального Docker-стека можно переопределить в `.env`:

```dotenv
APP_PORT=8000
POSTGRES_DB=type
POSTGRES_USER=type
POSTGRES_PASSWORD=type-local
DOCKER_SECRET_KEY=replace-with-at-least-32-random-characters
DOCKER_PUBLIC_URL=http://localhost:8000
DOCKER_TRUSTED_HOSTS=localhost,127.0.0.1
DOCKER_YANDEX_REDIRECT_URI=http://localhost:8000/auth/yandex/callback
```

Значения по умолчанию предназначены только для локальной машины. Перед
публичным развёртыванием задайте уникальные секреты, HTTPS URL и параметры
доверенного reverse proxy.

### Перенос существующей SQLite-базы

Импорт требует одинаковой актуальной Alembic-ревизии у источника и цели и
отказывается изменять PostgreSQL, если в нём уже есть данные. На время переноса
остановите основной контейнер приложения:

```bash
docker compose stop app
docker compose run --rm --user root \
  --volume "$(pwd)/instance/app.db:/tmp/source.db:ro" \
  app flask --app app sqlite_to_postgres /tmp/source.db
docker compose up -d app
```

Команда переносит данные одной транзакцией и синхронизирует PostgreSQL
sequences. Исходный SQLite-файл подключается в контейнер только для чтения.

### Резервная копия PostgreSQL

```bash
docker compose exec -T postgres pg_dump -U type -d type > type-backup.sql
docker compose exec -T postgres psql -U type -d type < type-backup.sql
```

При изменённых `POSTGRES_USER` и `POSTGRES_DB` подставьте соответствующие
значения в команды.

## Нативная установка
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
    SECRET_KEY=replace-with-at-least-32-random-characters
    DATABASE_URL=sqlite:///app.db
    FLASK_PORT=5000
    MAX_CONTENT_LENGTH=65536
    COOKIE_SAMESITE=Lax
    REMEMBER_COOKIE_DAYS=30
    YANDEX_CLIENT_ID=your-client-id
    YANDEX_CLIENT_SECRET=your-client-secret
    YANDEX_REDIRECT_URI=http://localhost:5000/auth/yandex/callback
    ANONYMOUS_ACTION_LIMIT=30
    PRACTICE_CARD_BATCH_SIZE=3
    PRACTICE_CARD_BATCH_MAX=12
    PRACTICE_DIFFICULT_CANDIDATE_LIMIT=50
    PRACTICE_SWIPE_GRACE_STRIKE=3
    RATE_LIMIT_STORAGE_URI=memory://
    ```
    В production (`DEBUG=false`) задайте общий backend rate limiter, например
    `RATE_LIMIT_STORAGE_URI=redis://localhost:6379/0`.
5. Примените миграции базы данных:
   ```bash
   flask --app app db upgrade
   ```
6. Заполните базу небольшим набором слов для разработки:
   ```bash
   flask --app app csv_to_db fixtures/test_words.csv
   ```

## Нативный запуск
1. Запустите проект:
    ```bash
    python run_dev.py
    ```

После изменения клиентского кода обновите минифицированную сборку:

```bash
scripts/build_static.sh
```

## Архитектура

Соглашения по структуре blueprint, URL, API и совместимости описаны в
[`docs/routing.md`](docs/routing.md).

Все задания имеют общий идентификатор в `PracticeItem`. Специфичные данные
хранятся в `SpellingExercise` и `ParonymExercise`, а пользовательские действия
ссылаются только на `practice_item_id`. API-типы этих упражнений — `spelling`
и `paronym`.

## Импорт данных

```bash
flask --app app csv_to_db path/to/words.csv
flask --app app txt_to_db path/to/paronyms.txt
flask --app app sentence_to_db path/to/sentences.txt
```

Формат строк орфографического CSV:
`слово_с_пропуском;правильный_ответ;вариант1,вариант2;категория`.
Правильный ответ указывается отдельно и должен входить в список вариантов.

В том же CSV можно описывать полноценные упражнения на паронимы:
`paronym;предложение_с_______;правильный_пароним;пароним1,пароним2;word_tags`.
Импорт создаёт или дополняет группу паронимов и связывает с ней упражнение.

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

Размер фоновой подгрузки ленты задаётся через `PRACTICE_CARD_BATCH_SIZE`, а
верхняя граница параметра API `limit` — через `PRACTICE_CARD_BATCH_MAX`.
Размер пула сложных кандидатов и длина серии без подтверждения пропуска
настраиваются через `PRACTICE_DIFFICULT_CANDIDATE_LIMIT` и
`PRACTICE_SWIPE_GRACE_STRIKE`.
В общей ленте орфографические и паронимические упражнения выбираются из
единого набора `PracticeItem` по одинаковым правилам.

## Ограничение частоты запросов

Все маршруты ограничены по частоте. Для OAuth, изменяющих запросов и отправки
сообщений действуют дополнительные, более строгие лимиты. Значения настраиваются
переменными `RATE_LIMIT_DEFAULT`, `RATE_LIMIT_APPLICATION`,
`RATE_LIMIT_AUTH`, `RATE_LIMIT_MUTATION` и `RATE_LIMIT_REPORT`.

Локально счётчики хранятся в памяти процесса. При запуске нескольких Gunicorn
worker-ов задайте общее хранилище, например
`RATE_LIMIT_STORAGE_URI=redis://localhost:6379/0`.
Если Flask находится за reverse proxy, укажите точное число доверенных прокси
в `TRUSTED_PROXY_COUNT`; не включайте доверие к `X-Forwarded-For` без прокси.

## Администратор

ID текущего пользователя показан на странице настроек. Выдать ему права администратора:

```sql
UPDATE "user" SET is_admin = TRUE WHERE id = <USER_ID>;
```

Отозвать права:

```sql
UPDATE "user" SET is_admin = FALSE WHERE id = <USER_ID>;
```

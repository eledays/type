
![Poster](https://github.com/eledays/type/blob/main/app/static/img/post.png)

## Описание
**type** — бесконечная лента слов в формате ТикТок для подготовки к ЕГЭ по русскому языку. В каждом слове есть один пропуск, который нужно правильно заполнить одним из вариантов внизу экрана.

[**Style guide**](https://www.figma.com/design/dXQn6Ubr9HdIShHxYmXppK/type-%E2%80%93-style-guide?node-id=0-1&t=HydzOxkpEAnHfhth-1)

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
3. Настройте `.env` по примеру `.env.example`
4. Установите [Docker](https://www.docker.com/)
5. Соберите и поднимите контейнеры
```bash
docker compose up -d --build
```
6. Посмотреть логи
```bash
docker compose logs -f type-app
```

## Перенос БД с sqlite
```bash
sudo apt install pgloader
source .env
pgloader sqlite:///путь/до/бд/app.db postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:${POSTGRES_PORT}/${POSTGRES_DB}
```

## Наполнение базы данных

📖 **[Подробная документация по формату данных](docs/database/data-format.md)**


## Использование
1. Поднимите контейнер:
```bash
docker compose up -d
```
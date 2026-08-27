# Запуск Type в production

Эта инструкция рассчитана на один Linux-сервер с Docker Engine и плагином
Docker Compose. Выполняйте шаги по порядку из корня репозитория. В примерах
приложение размещается в `/opt/type`.

Production-стек состоит из:

- Nginx — единственный публичный сервис, порты `80` и `443`;
- Certbot — выпуск и продление сертификата Let's Encrypt;
- Gunicorn-приложение — доступно только Nginx внутри Docker-сети;
- PostgreSQL и Redis — без опубликованных наружу портов.

> Не запускайте в production обычный `docker compose up`: локальный override
> публикует порт приложения `8000`. Используйте только скрипты из этой
> инструкции.

## 1. Подготовить сервер

Понадобятся:

- 64-битный Linux-сервер с минимум 2 ГБ RAM;
- Docker Engine и Docker Compose plugin;
- домен, направленный на публичный IP сервера;
- открытые входящие TCP-порты `22`, `80` и `443`.

Проверьте Docker:

```bash
docker --version
docker compose version
docker run --rm hello-world
```

Установите Docker из официального репозитория для своего дистрибутива, если
эти команды не работают. Пользователь деплоя должен иметь доступ к Docker —
напрямую или через `sudo`.

Создайте DNS-запись `A`, указывающую на IPv4 сервера. Запись `AAAA` добавляйте
только при настроенных IPv6-маршрутизации и firewall. Проверить DNS можно с
рабочего компьютера:

```bash
dig +short A example.com
dig +short AAAA example.com
```

Замените `example.com` своим доменом. Перед выпуском сертификата домен должен
уже открывать этот сервер по порту `80`. Порты `8000`, `5432` и `6379`
открывать не нужно.

## 2. Получить код

На сервере:

```bash
sudo mkdir -p /opt/type
sudo chown "$USER":"$USER" /opt/type
git clone https://github.com/eledays/type.git /opt/type
cd /opt/type
```

Все дальнейшие команды выполняйте из `/opt/type`.

## 3. Настроить production-переменные

Создайте закрытый env-файл:

```bash
cp .env.production.example .env.production
chmod 600 .env.production
```

Сгенерируйте два разных секрета:

```bash
openssl rand -hex 32
openssl rand -hex 32
```

Откройте `.env.production` и замените все значения-заглушки:

```bash
nano .env.production
```

Пример структуры файла:

```dotenv
DOMAIN=example.com
CERTBOT_EMAIL=admin@example.com

SECRET_KEY=<первый-сгенерированный-секрет>
POSTGRES_DB=type
POSTGRES_USER=type
POSTGRES_PASSWORD=<второй-сгенерированный-секрет>

YANDEX_CLIENT_ID=<id-приложения-яндекс>
YANDEX_CLIENT_SECRET=<секрет-приложения-яндекс>
```

Требования к значениям:

- `DOMAIN` — только имя хоста, без `https://`, пути и завершающего `/`;
- `CERTBOT_EMAIL` — действующий адрес для уведомлений Let's Encrypt;
- `SECRET_KEY` и `POSTGRES_PASSWORD` — разные случайные значения;
- значения нельзя заключать в `<` и `>` — они показаны только как маркеры;
- `.env.production` нельзя добавлять в Git.

В настройках приложения Яндекс OAuth укажите точный callback URL:

```text
https://example.com/auth/yandex/callback
```

## 4. Проверить конфигурацию

```bash
scripts/compose_production.sh config --quiet
```

Команда без вывода и с кодом возврата `0` означает, что Compose-конфигурация
валидна. Если переменная не заполнена, команда покажет её имя.

Дополнительно убедитесь, что порты не заняты другим reverse proxy:

```bash
sudo ss -lntp | awk '$4 ~ /:(80|443)$/ {print}'
```

Если в выводе есть Apache, Caddy или другой Nginx, сначала остановите именно
этот старый сервис. Не останавливайте SSH.

## 5. Первый запуск и HTTPS

Запускайте этот шаг только после обновления DNS и открытия портов `80/443`:

```bash
scripts/init_tls.sh
```

Скрипт:

1. собирает приложение и Nginx;
2. запускает PostgreSQL, Redis, приложение и Nginx во временном HTTP-режиме;
3. получает сертификат Let's Encrypt через HTTP challenge;
4. пересоздаёт только Nginx уже в HTTPS-режиме.

Запрос сертификата может завершиться ошибкой, если домен указывает не на этот
сервер, порт `80` закрыт или на нём отвечает другой сервис. После исправления
причины безопасно запустите `scripts/init_tls.sh` ещё раз.

## 6. Проверить запуск

Состояние контейнеров:

```bash
scripts/compose_production.sh ps
```

Сервисы `app`, `postgres`, `redis` и `nginx` должны иметь состояние `Up`, а
контейнеры с healthcheck — перейти в `healthy`.

Проверьте логи:

```bash
scripts/compose_production.sh logs --tail=200 app nginx postgres redis
```

Проверьте приложение с другой машины:

```bash
curl --fail --show-error https://example.com/health/live
curl --fail --show-error https://example.com/health/ready
curl --head http://example.com
```

Ожидаемый результат:

- `/health/live` возвращает `200` и подтверждает работу веб-процесса;
- `/health/ready` возвращает `200` и подтверждает доступность PostgreSQL и Redis;
- HTTP-запрос перенаправляется на HTTPS с кодом `308`;
- браузер показывает действительный сертификат для домена.

Если `ready` не отвечает, смотрите логи приложения:

```bash
scripts/compose_production.sh logs --tail=300 app
```

## 7. Данные

При первом старте Alembic-миграции применяются автоматически до запуска
Gunicorn. Новая база данных будет пустой.

Для тестового наполнения можно выполнить:

```bash
scripts/compose_production.sh exec -T app \
  flask --app app csv_to_db fixtures/test_words.csv
```

Для production-данных передайте файлы в `/opt/type`, ограничьте к ним доступ и
передайте содержимое каждой команды через стандартный ввод:

```bash
chmod 600 words.csv paronyms.txt sentences.txt

scripts/compose_production.sh run --rm --no-deps -T \
  app flask --app app csv_to_db /dev/stdin < words.csv

scripts/compose_production.sh run --rm --no-deps -T \
  app flask --app app txt_to_db /dev/stdin < paronyms.txt

scripts/compose_production.sh run --rm --no-deps -T \
  app flask --app app sentence_to_db /dev/stdin < sentences.txt
```

Выполняйте только команды для реально имеющихся типов данных. После успешного
импорта удалите или перенесите исходные файлы в закрытое хранилище. Не
коммитьте пользовательские данные.

Перенос существующей PostgreSQL-базы подробно описан в
[`deployment.md`](deployment.md#4-moving-the-existing-data).

## 8. Настроить автоматическое продление сертификата

Проверьте скрипт вручную:

```bash
scripts/renew_tls.sh
```

Certbot обновляет сертификат только близко к окончанию срока, после чего Nginx
перечитывает сертификаты. Добавьте ежедневный запуск в root crontab:

```bash
sudo crontab -e
```

Добавьте строку:

```cron
17 3 * * * cd /opt/type && ./scripts/renew_tls.sh >> /var/log/type-certbot.log 2>&1
```

Проверьте, что запись сохранилась:

```bash
sudo crontab -l
```

## 9. Резервное копирование

Создать PostgreSQL dump:

```bash
cd /opt/type
scripts/backup_postgres.sh
```

Файл появится в `backups/` с правами только для владельца. Регулярно копируйте
backup за пределы этого сервера: локальная копия не спасёт при потере VPS или
диска.

Не используйте на production команду:

```text
docker compose down --volumes
```

Она удаляет volumes PostgreSQL, Redis и Let's Encrypt вместе с данными.

## 10. Выпустить обновление

Перед каждым обновлением:

```bash
cd /opt/type
scripts/backup_postgres.sh
git pull --ff-only
scripts/compose_production.sh build app nginx
scripts/compose_production.sh up --detach
scripts/compose_production.sh ps
curl --fail --show-error https://example.com/health/ready
```

После обновления просмотрите свежие логи:

```bash
scripts/compose_production.sh logs --since=10m app nginx
```

Миграции базы применяются контейнером приложения автоматически.

## 11. Полезные команды

Следить за логами:

```bash
scripts/compose_production.sh logs --follow app nginx
```

Перезапустить приложение:

```bash
scripts/compose_production.sh restart app
```

Пересобрать и пересоздать приложение после изменения кода:

```bash
scripts/compose_production.sh up --build --detach app
```

Остановить стек без удаления данных:

```bash
scripts/compose_production.sh down
```

Запустить его снова:

```bash
scripts/compose_production.sh up --detach
```

## 12. Быстрая диагностика

### Certbot не получил сертификат

Проверьте:

```bash
dig +short A example.com
curl --verbose http://example.com/.well-known/acme-challenge/test
scripts/compose_production.sh logs --tail=200 nginx
```

Ответ `404` для тестового challenge-файла допустим: важно, чтобы он пришёл с
этого Nginx, а не от другого сервера. После исправления DNS/firewall повторите
`scripts/init_tls.sh`.

### Nginx возвращает 502 или 504

```bash
scripts/compose_production.sh ps
scripts/compose_production.sh logs --tail=300 app postgres redis nginx
```

Чаще всего приложение ещё запускается, не прошла миграция или недоступны
PostgreSQL/Redis.

### OAuth возвращает ошибку redirect URI

Сравните три значения — они должны использовать один и тот же домен:

- `DOMAIN` в `.env.production`;
- callback в Яндекс OAuth;
- фактический адрес `https://<DOMAIN>/auth/yandex/callback`.

После изменения `.env.production` пересоздайте приложение:

```bash
scripts/compose_production.sh up --detach --force-recreate app
```

## Финальный чек-лист

- [ ] DNS домена указывает на production-сервер.
- [ ] Открыты только необходимые публичные порты `22`, `80`, `443`.
- [ ] `.env.production` заполнен и имеет права `600`.
- [ ] Callback Яндекс OAuth совпадает с production URL.
- [ ] Все четыре основных контейнера запущены и healthy.
- [ ] `/health/live` и `/health/ready` возвращают `200` по HTTPS.
- [ ] HTTP перенаправляется на HTTPS.
- [ ] В браузере действителен TLS-сертификат.
- [ ] Настроен ежедневный `renew_tls.sh`.
- [ ] Создан backup и настроено его внешнее хранение.

# Production: Apache на отдельном reverse-proxy сервере

Эта инструкция описывает запуск Type на двух машинах:

```text
Интернет
   │ HTTPS :443
   ▼
Apache reverse proxy (10.0.0.10)
   │ HTTP :8000, только приватная сеть/VPN
   ▼
Type + PostgreSQL + Redis (10.0.0.20)
```

В примерах:

- публичный домен — `example.com`;
- приватный IP Apache-сервера — `10.0.0.10`;
- приватный IP сервера приложения — `10.0.0.20`;
- origin-порт приложения — `8000`;
- репозиторий на сервере приложения — `/opt/type`.

Замените эти значения своими. DNS домена должен указывать на публичный IP
Apache-сервера, а не на сервер приложения.

> Соединение Apache → Type использует HTTP. Оно должно идти только по
> доверенной приватной сети или VPN, например WireGuard. Не передавайте
> пользовательский трафик между серверами открытым HTTP через интернет.

## Можно ли запустить без reverse proxy

Да, для локальной разработки и проверки. Обычный Compose-файл запускает
приложение напрямую на `http://localhost:8000`:

```bash
docker compose up --build --detach
curl --fail http://localhost:8000/health/ready
```

Этот режим не требует Apache, Nginx или сертификата и использует настройки для
разработки. Он описан в основном [`README.md`](../README.md#запуск-через-docker-compose).

Для публичного production-запуска reverse proxy или балансировщик с HTTPS
обязателен. Production Compose включает secure cookies, HSTS, HTTPS callback
Яндекс OAuth и доверие к proxy-заголовкам. Если открыть origin по обычному HTTP
напрямую в интернет, авторизация и сессии будут работать некорректно, а клиенты
смогут подделывать доверенные заголовки.

Вместо Apache можно использовать другой доверенный HTTPS reverse proxy или
облачный load balancer. Он должен:

- сохранять публичный заголовок `Host`;
- добавлять реальный адрес клиента в `X-Forwarded-For`;
- устанавливать `X-Forwarded-Proto: https`;
- быть единственным узлом, которому доступен origin-порт.

Дальнейшие шаги этой инструкции относятся именно к production-схеме с Apache.

## 1. Подготовить сеть

Проверьте связность приватных адресов:

На Apache-сервере:

```bash
ping -c 3 10.0.0.20
```

На сервере приложения:

```bash
ping -c 3 10.0.0.10
```

Правила доступа должны быть такими:

| Назначение | Источник | Порт |
|---|---|---:|
| Apache | интернет | `80`, `443` |
| Type | только Apache `10.0.0.10` | `8000` |
| PostgreSQL и Redis | только Docker-сеть | не публикуются |

Если на сервере приложения уже используется UFW, разрешите origin-порт только
от Apache. Сначала убедитесь, что SSH уже разрешён:

```bash
sudo ufw status numbered
sudo ufw allow proto tcp from 10.0.0.10 to 10.0.0.20 port 8000
sudo ufw status numbered
```

Не добавляйте общее правило `allow 8000/tcp`.

## 2. Установить приложение

На сервере приложения должны быть установлены Docker Engine и Docker Compose
plugin. Проверьте их:

```bash
docker --version
docker compose version
docker run --rm hello-world
```

Получите код:

```bash
sudo mkdir -p /opt/type
sudo chown "$USER":"$USER" /opt/type
git clone https://github.com/eledays/type.git /opt/type
cd /opt/type
```

## 3. Заполнить `.env.production`

На сервере приложения:

```bash
cd /opt/type
cp .env.production.example .env.production
chmod 600 .env.production
openssl rand -hex 32
openssl rand -hex 32
nano .env.production
```

Два вызова OpenSSL должны дать разные значения для `SECRET_KEY` и
`POSTGRES_PASSWORD`.

Пример готового файла:

```dotenv
DOMAIN=example.com
APP_BIND_IP=10.0.0.20
APP_PORT=8000

SECRET_KEY=вставьте-первый-сгенерированный-секрет
POSTGRES_DB=type
POSTGRES_USER=type
POSTGRES_PASSWORD=вставьте-второй-сгенерированный-секрет

YANDEX_CLIENT_ID=идентификатор-приложения
YANDEX_CLIENT_SECRET=секрет-приложения
```

Правила:

- `DOMAIN` — публичный домен без `https://` и пути;
- `APP_BIND_IP` — приватный/VPN IP именно сервера приложения;
- `APP_PORT` — порт, к которому будет подключаться Apache;
- не добавляйте кавычки и маркеры `<...>` вокруг значений;
- никогда не коммитьте `.env.production`.

В Яндекс OAuth зарегистрируйте точный callback:

```text
https://example.com/auth/yandex/callback
```

## 4. Запустить origin-сервер

Проверить итоговую конфигурацию:

```bash
cd /opt/type
scripts/compose_production.sh config --quiet
```

Если команда завершилась без вывода, запустите стек:

```bash
scripts/compose_production.sh up --build --detach
scripts/compose_production.sh ps
```

Должны работать три сервиса: `app`, `postgres`, `redis`. Контейнеры с
healthcheck должны перейти в состояние `healthy`.

Проверьте origin на сервере приложения:

```bash
curl --fail --show-error \
  --header 'Host: example.com' \
  http://10.0.0.20:8000/health/ready
```

Ожидаемый ответ:

```json
{"status":"ok"}
```

Проверьте, что порт слушает только нужный адрес:

```bash
sudo ss -lntp | awk '$4 ~ /:8000$/ {print}'
```

В выводе должен быть `10.0.0.20:8000`, а не `0.0.0.0:8000`.

## 5. Проверить origin с Apache-сервера

На Apache-сервере:

```bash
curl --fail --show-error \
  --header 'Host: example.com' \
  http://10.0.0.20:8000/health/ready
```

Не переходите дальше, пока этот запрос не возвращает `200`. Если соединение не
устанавливается, проверьте приватный маршрут, firewall и `APP_BIND_IP`. Если
возвращается `400`, проверьте `DOMAIN` и заголовок `Host`.

## 6. Подготовить Apache

Дальнейшие команды выполняются на отдельном Apache-сервере. Пример рассчитан
на Debian/Ubuntu:

```bash
sudo apt update
sudo apt install apache2 certbot
sudo a2enmod proxy proxy_http headers rewrite ssl deflate
sudo mkdir -p /var/www/type-certbot/.well-known/acme-challenge
```

Скопируйте из репозитория шаблоны на Apache-сервер. Например, с сервера
приложения:

```bash
scp /opt/type/deploy/apache/type-http.conf.example \
  proxy-admin@10.0.0.10:/tmp/type-http.conf
scp /opt/type/deploy/apache/type.conf.example \
  proxy-admin@10.0.0.10:/tmp/type.conf
```

Вместо `proxy-admin` укажите пользователя Apache-сервера.

## 7. Получить TLS-сертификат на Apache-сервере

Сначала установите временный HTTP VirtualHost:

```bash
sudo cp /tmp/type-http.conf /etc/apache2/sites-available/type-http.conf
sudo nano /etc/apache2/sites-available/type-http.conf
```

Замените `example.com` на production-домен, затем:

```bash
sudo a2ensite type-http.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```

Проверьте DNS с любой внешней машины:

```bash
dig +short A example.com
curl --verbose http://example.com/.well-known/acme-challenge/test
```

Ответ `404` на второй запрос допустим. Важно, чтобы запрос пришёл на нужный
Apache-сервер. Получите сертификат:

```bash
sudo certbot certonly \
  --webroot \
  --webroot-path /var/www/type-certbot \
  --domain example.com \
  --email admin@example.com \
  --agree-tos \
  --no-eff-email
```

Не запускайте эту команду многократно без исправления ошибки: Let's Encrypt
ограничивает частоту запросов сертификатов.

## 8. Включить reverse proxy

Установите основной VirtualHost:

```bash
sudo cp /tmp/type.conf /etc/apache2/sites-available/type.conf
sudo nano /etc/apache2/sites-available/type.conf
```

В файле замените:

- все `example.com` на публичный домен;
- `10.0.0.20:8000` на приватный адрес и порт сервера приложения.

Проверьте и включите конфигурацию:

```bash
sudo apache2ctl configtest
sudo a2dissite type-http.conf
sudo a2ensite type.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```

Готовый шаблон находится в
[`deploy/apache/type.conf.example`](../deploy/apache/type.conf.example). Он:

- перенаправляет HTTP на HTTPS кодом `308`;
- оставляет HTTP-доступ к ACME challenge для продления сертификата;
- сохраняет публичный `Host`;
- передаёт клиентский IP и фиксированный `X-Forwarded-Proto: https`;
- проксирует запросы на приватный origin;
- ограничивает тело запроса размером 64 КиБ.

## 9. Финальная проверка

С внешней машины:

```bash
curl --fail --show-error https://example.com/health/live
curl --fail --show-error https://example.com/health/ready
curl --head http://example.com
```

Ожидается:

- оба health endpoint возвращают `200`;
- HTTP возвращает `308` с переходом на HTTPS;
- браузер показывает действительный сертификат;
- вход через Яндекс возвращает пользователя на production-домен.

На Apache-сервере проверьте логи:

```bash
sudo tail -n 200 /var/log/apache2/type-error.log
sudo tail -n 200 /var/log/apache2/type-access.log
```

На сервере приложения:

```bash
cd /opt/type
scripts/compose_production.sh logs --tail=200 app postgres redis
```

## 10. Продление сертификата

Сертификат и Certbot находятся только на Apache-сервере. Пакет обычно включает
systemd timer. Проверьте его:

```bash
sudo systemctl list-timers --all certbot.timer
sudo certbot renew --dry-run
```

Apache перечитывает обновлённый сертификат через стандартный deploy hook
пакета. Если в вашей системе hook отсутствует, создайте его:

```bash
sudo sh -c 'printf "%s\n" "#!/bin/sh" "systemctl reload apache2" > /etc/letsencrypt/renewal-hooks/deploy/reload-apache.sh'
sudo chmod 755 /etc/letsencrypt/renewal-hooks/deploy/reload-apache.sh
```

На сервере приложения Certbot не нужен.

## 11. Загрузить данные

Миграции применяются автоматически перед запуском Gunicorn. Новая база будет
пустой. Тестовый набор можно загрузить так:

```bash
cd /opt/type
scripts/compose_production.sh exec -T app \
  flask --app app csv_to_db fixtures/test_words.csv
```

Для собственных файлов передайте содержимое через stdin:

```bash
chmod 600 words.csv paronyms.txt sentences.txt

scripts/compose_production.sh run --rm --no-deps -T \
  app flask --app app csv_to_db /dev/stdin < words.csv

scripts/compose_production.sh run --rm --no-deps -T \
  app flask --app app txt_to_db /dev/stdin < paronyms.txt

scripts/compose_production.sh run --rm --no-deps -T \
  app flask --app app sentence_to_db /dev/stdin < sentences.txt
```

Выполняйте только нужные команды. После импорта удалите исходные файлы или
перенесите их в закрытое хранилище.

## 12. Резервное копирование

На сервере приложения:

```bash
cd /opt/type
scripts/backup_postgres.sh
```

Dump появится в `backups/`. Регулярно копируйте его на другую машину или в
объектное хранилище.

Никогда не выполняйте в production:

```text
docker compose down --volumes
```

Эта команда удаляет volumes PostgreSQL и Redis вместе с данными.

## 13. Выпустить обновление приложения

Apache и сертификат при обычном релизе не меняются. На сервере приложения:

```bash
cd /opt/type
scripts/backup_postgres.sh
git pull --ff-only
scripts/compose_production.sh build app
scripts/compose_production.sh up --detach
scripts/compose_production.sh ps
curl --fail --show-error \
  --header 'Host: example.com' \
  http://10.0.0.20:8000/health/ready
```

Затем с внешней машины:

```bash
curl --fail --show-error https://example.com/health/ready
```

## 14. Диагностика

### Apache возвращает 502 или 504

На Apache-сервере повторите прямой запрос к origin:

```bash
curl --verbose --header 'Host: example.com' \
  http://10.0.0.20:8000/health/ready
sudo tail -n 200 /var/log/apache2/type-error.log
```

На сервере приложения:

```bash
scripts/compose_production.sh ps
scripts/compose_production.sh logs --tail=300 app postgres redis
```

### Приложение возвращает 400 Invalid Host

Убедитесь, что:

- Apache использует `ProxyPreserveHost On`;
- `DOMAIN` в `.env.production` совпадает с публичным доменом;
- после изменения env контейнер пересоздан:

```bash
scripts/compose_production.sh up --detach --force-recreate app
```

### В логах неверный IP клиента или генерируются HTTP-ссылки

Проверьте, что Apache использует `ProxyAddHeaders On` и передаёт фиксированный
`X-Forwarded-Proto: https`. Приложение настроено доверять ровно одному proxy
hop (`TRUSTED_PROXY_COUNT=1`). Origin-порт нельзя открывать для произвольных
клиентов: иначе они смогут подделывать доверенные proxy-заголовки.

## Финальный чек-лист

- [ ] DNS указывает на Apache-сервер.
- [ ] Между серверами используется приватная сеть или VPN.
- [ ] Порт origin доступен только с IP Apache.
- [ ] PostgreSQL и Redis не публикуют порты.
- [ ] `.env.production` имеет права `600` и не попал в Git.
- [ ] Apache передаёт `Host`, `X-Forwarded-For` и `X-Forwarded-Proto`.
- [ ] `/health/live` и `/health/ready` возвращают `200` через HTTPS.
- [ ] HTTP перенаправляется на HTTPS.
- [ ] Callback Яндекс OAuth совпадает с production URL.
- [ ] Certbot timer работает на Apache-сервере.
- [ ] Backup хранится за пределами сервера приложения.

# Деплой на VPS

Инструкция под сервер вида 1 vCPU / 2 ГБ RAM / 25 ГБ NVMe (Selectel, Ubuntu
22.04 или 24.04) и под то, что на этом же сервере будут жить соседние
инструменты.

## Схема

```
Интернет → Caddy на хосте (80/443, SSL)
             ├── slovostat.example.com → 127.0.0.1:8000 → контейнер slovostat
             ├── domains.example.com   → 127.0.0.1:8001 → контейнер другого инструмента
             └── dr.example.com        → 127.0.0.1:8002 → ...
```

Reverse proxy один на все сервисы, каждый инструмент — отдельный каталог в
`/opt` со своим `docker-compose.yml` и своим портом на `127.0.0.1`. Наружу
контейнеры не смотрят.

## Сколько ресурсов нужно

Замеры SlovoStat (разбор страницы — самая тяжёлая операция):

| | RAM | CPU |
|---|---|---|
| Простой (контейнер) | ~40 МБ | ~0 |
| Страница 300 КБ (типичная) | +7 МБ | 0,1 с |
| Страница 5 МБ (лимит) | +82 МБ | 1,5 с |

То есть один инструмент — это ~60 МБ в покое и до ~150 МБ на пике. Плюс
система и Docker (~250 МБ) и Caddy (~30 МБ). На 2 ГБ спокойно помещается
5–6 таких сервисов; узкое место — не память, а единственное ядро: разбор
крупной страницы занимает его целиком на секунду-полторы.

Отсюда два правила: в compose у каждого сервиса стоит `mem_limit`, чтобы один
инструмент не уронил соседей, и на сервере нужен swap — на 2 ГБ без него любой
всплеск заканчивается OOM-killer'ом.

Диска 25 ГБ хватает с запасом: образ ~240 МБ на инструмент, база рейт-лимита —
десятки килобайт. Следить стоит только за тем, чтобы старые образы не копились
(см. «Обслуживание»).

## 1. Первая настройка сервера

Под root сразу после создания машины.

```bash
# Пользователь вместо root; пароль не нужен, вход только по ключу
adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy
echo 'deploy ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/deploy && chmod 440 /etc/sudoers.d/deploy
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy/

# Swap 2 ГБ — обязательный для 2 ГБ RAM
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
sysctl -w vm.swappiness=10 && echo 'vm.swappiness=10' >> /etc/sysctl.conf

# Файрвол
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable

# Автообновления безопасности (без интерактивного диалога)
apt-get install -y unattended-upgrades
printf 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n' \
  > /etc/apt/apt.conf.d/20auto-upgrades
```

Вход по ключу закрывается **отдельным шагом и только после проверки**. На
облачных образах Ubuntu настройки SSH приходят из `/etc/ssh/sshd_config.d/`, и
правка самого `sshd_config` ничего не даст: в sshd побеждает первое значение, а
`50-cloud-init.conf` читается раньше. Поэтому нужен drop-in с меньшим номером:

```bash
printf 'PasswordAuthentication no\nPermitRootLogin no\nKbdInteractiveAuthentication no\n' \
  > /etc/ssh/sshd_config.d/00-hardening.conf
sshd -t && systemctl reload ssh
sshd -T | grep -Ei 'passwordauthentication|permitrootlogin'   # должно быть no/no
```

Перед этим открой второе SSH-соединение под `deploy` и убедись, что оно
работает. Первую сессию под root не закрывай, пока не проверишь.

`ufw` не фильтрует порты, опубликованные Docker'ом, — но в нашем compose они
публикуются только на `127.0.0.1`, так что снаружи их всё равно не видно.

## 2. Docker

```bash
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
usermod -aG docker deploy
```

## 3. Приложение

Дальше — под пользователем `deploy`.

```bash
sudo install -d -o deploy -g deploy /opt/slovostat
git clone https://github.com/kotophalk/slovostat.git /opt/slovostat
cd /opt/slovostat
cp .env.example .env      # порт и лимиты — при необходимости поправить
docker compose up -d --build
```

Проверка до всякого домена:

```bash
curl -s -X POST http://127.0.0.1:8000/analyze \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com"}'
# {"words":19,"chars":127,"chars_no_spaces":109}
```

База лежит в `/opt/slovostat/data/slovostat.db` (том смонтирован в контейнер),
переменные окружения — в `.env`, полный список в [configuration.md](configuration.md).

## 4. Caddy и домен

```bash
sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update && sudo apt-get install -y caddy
```

Готовый конфиг для `slovostat.ru` лежит в [`deploy/Caddyfile`](../deploy/Caddyfile)
(шаблон под другой домен — в [`deploy/Caddyfile.example`](../deploy/Caddyfile.example)):

```bash
sudo cp /opt/slovostat/deploy/Caddyfile /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

DNS: A-запись `slovostat.ru` → IP сервера, такая же для `www`. Если
инструментов будет несколько, проще сразу завести wildcard `*.slovostat.ru` →
тот же IP: новый сервис тогда добавляется одним блоком в Caddyfile без похода
в DNS. Сертификат Caddy получит сам при первом обращении — но только после
того, как DNS реально начнёт резолвиться.

## 5. Проверка, что лимит считает по клиентам

За прокси IP берётся из `X-Forwarded-For` (его добавляет Caddy), и принимается
он только от доверенных адресов. Контейнер видит прокси как адрес
docker-шлюза (`172.17.0.1`), он входит в список по умолчанию — руками ничего
настраивать не нужно. Убедиться, что в базу пишутся реальные адреса, а не
`127.0.0.1`:

```bash
sudo apt-get install -y sqlite3
sqlite3 /opt/slovostat/data/slovostat.db 'SELECT ip, COUNT(*) FROM requests GROUP BY ip;'
```

Если там один-единственный внутренний адрес — значит, заголовок не доходит:
проверь, что запросы идут через Caddy, а не напрямую на порт.

## Обновление

```bash
cd /opt/slovostat && git pull && docker compose up -d --build && docker image prune -f
```

## Резервные копии

В базе лежат только счётчики рейт-лимита — потеря означает лишь сброс суточных
квот, так что бэкап не обязателен. Если всё же нужен:

```bash
sqlite3 /opt/slovostat/data/slovostat.db ".backup '/opt/backups/slovostat-$(date +%F).db'"
```

Простое копирование файла при включённом WAL небезопасно — только `.backup`.

## Добавить следующий инструмент

1. `git clone` в `/opt/<имя>`, свой `.env` с портом 8001, 8002, …
2. В compose нового сервиса — тот же `mem_limit` и публикация на `127.0.0.1`.
3. Блок в `/etc/caddy/Caddyfile` по образцу, `systemctl reload caddy`.

## Обслуживание

```bash
docker compose logs -f --tail 100      # логи приложения
docker stats --no-stream               # память и CPU по контейнерам
free -h                                # не съеден ли swap
sudo journalctl -u caddy -n 50         # проблемы с сертификатами
docker system prune -af --volumes      # чистка старых образов (тома проекта не трогает)
```

Ротация логов приложения уже настроена в compose (3 файла по 10 МБ), логов
Caddy — в примере конфига.

## Если вместо Caddy нужен Nginx

Тот же принцип, больше ручной работы: сертификаты через certbot, заголовки
прописываются явно.

```nginx
server {
    listen 80;
    server_name slovostat.example.com;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://$host$request_uri; }
}

server {
    listen 443 ssl;
    server_name slovostat.example.com;

    ssl_certificate     /etc/letsencrypt/live/slovostat.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/slovostat.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo apt-get install -y nginx certbot python3-certbot-nginx
sudo ln -s /etc/nginx/sites-available/slovostat /etc/nginx/sites-enabled/
sudo certbot --nginx -d slovostat.example.com
```

| | Caddy | Nginx |
|---|---|---|
| SSL | автоматически | certbot + таймер |
| Конфиг на сервис | 3 строки | ~25 строк |
| Новый инструмент | блок + reload | конфиг + certbot |

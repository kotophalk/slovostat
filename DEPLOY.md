# Деплой SlovoStat на VPS

## Архитектура

```
Интернет → Caddy/Nginx (80/443, SSL) → Docker (127.0.0.1:8000)
```

---

## 1. docker-compose.yml

Создать в корне проекта:

```yaml
services:
  app:
    build: .
    restart: unless-stopped
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - ./data:/app/data
    environment:
      - SLOVOSTAT_DB_PATH=/app/data/slovostat.db
```

Приложение слушает только на localhost:8000 — наружу его выставляет reverse proxy.

---

## 2. Вариант A: Caddy (рекомендуется)

Caddy сам получает и обновляет Let's Encrypt сертификат. Ноль конфигурации для SSL.

`/etc/caddy/Caddyfile` на VPS:

```
slovostat.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

Замени `slovostat.example.com` на свой домен.

---

## 3. Вариант B: Nginx + Certbot

`/etc/nginx/sites-available/slovostat` на VPS:

```nginx
server {
    listen 80;
    server_name slovostat.example.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name slovostat.example.com;

    ssl_certificate /etc/letsencrypt/live/slovostat.example.com/fullchain.pem;
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

---

## 4. Скрипт первоначальной настройки VPS (deploy.sh)

```bash
#!/bin/bash
set -e

echo "=== Установка Docker ==="
apt-get update
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

echo "=== Вариант: Caddy ==="
# Раскомментируй если выбрал Caddy:
# apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
# curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
# curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
# apt-get update
# apt-get install -y caddy

echo "=== Вариант: Nginx + Certbot ==="
# Раскомментируй если выбрал Nginx:
# apt-get install -y nginx certbot python3-certbot-nginx
# ln -s /etc/nginx/sites-available/slovostat /etc/nginx/sites-enabled/
# certbot --nginx -d slovostat.example.com

echo "=== Запуск приложения ==="
cd /opt/slovostat
docker compose up -d --build

echo "=== Готово ==="
```

---

## Порядок деплоя

1. **Скопировать проект на VPS:**
   ```bash
   scp -r . user@your-vps:/opt/slovostat
   ```

2. **На VPS — запустить скрипт (от root):**
   ```bash
   ssh user@your-vps
   cd /opt/slovostat
   sudo bash deploy.sh
   ```

3. **DNS** — направить A-запись домена на IP VPS

4. **Caddy** — после того как DNS заработает:
   ```bash
   sudo systemctl restart caddy
   ```
   Или **Nginx**:
   ```bash
   sudo certbot --nginx -d slovostat.example.com
   sudo systemctl restart nginx
   ```

---

## Сравнение вариантов

| Компонент | Caddy | Nginx |
|-----------|-------|-------|
| SSL | автоматически | certbot + cron |
| Конфиг | 3 строки | ~25 строк |
| Сложность | минимальная | средняя |

Рекомендация: **Caddy** — три строки конфига, SSL из коробки, автопродление.

Когда определишься с доменом — замени `slovostat.example.com` на свой.

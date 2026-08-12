#!/bin/bash
# Обновление боевой копии до состояния origin/master.
#
# Запускается двумя способами:
#   - из GitHub Actions по SSH (в authorized_keys прописан как forced command,
#     поэтому ключ деплоя не может выполнить ничего другого);
#   - руками: /opt/slovostat/deploy/update.sh
set -euo pipefail

cd /opt/slovostat

PORT="$(sed -n 's/^SLOVOSTAT_PORT=//p' .env 2>/dev/null | head -1)"
PORT="${PORT:-8000}"

echo "=== git ==="
git fetch --prune origin
# ff-only: если на сервере оказались локальные правки, деплой упадёт заметно,
# а не затрёт их молча.
git pull --ff-only

echo "=== сборка и запуск ==="
docker compose up -d --build
docker image prune -f

echo "=== состояние ==="
docker compose ps

echo "=== проверка здоровья ==="
for _ in $(seq 20); do
	if curl -sf --max-time 2 "http://127.0.0.1:${PORT}/health" > /dev/null; then
		echo "сервис отвечает"
		exit 0
	fi
	sleep 1
done

echo "сервис не поднялся: /health молчит 20 секунд" >&2
docker compose logs --tail 50
exit 1

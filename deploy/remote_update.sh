#!/usr/bin/env bash
# รันบน VPS (เรียกจาก push.sh) — ติดตั้ง dependency, migrate, collectstatic, ตรวจ deploy แล้วรีสตาร์ท
set -euo pipefail
ROOT=/srv/letmehelp
APP=$ROOT/app
export DJANGO_SETTINGS_MODULE=config.settings.production
cd "$APP"

[ -d "$ROOT/venv" ] || python3 -m venv "$ROOT/venv"
"$ROOT/venv/bin/pip" install -q --upgrade pip
"$ROOT/venv/bin/pip" install -q -r requirements.txt

PY="$ROOT/venv/bin/python"
$PY manage.py check --deploy --fail-level WARNING
$PY manage.py migrate --noinput
$PY manage.py collectstatic --noinput -v 0

sudo /usr/bin/systemctl restart letmehelp-web letmehelp-worker letmehelp-beat
sleep 3
# health check ผ่าน gunicorn ตรง (ข้าม nginx) — ต้องได้ 200/301
code=$(curl -s -o /dev/null -w '%{http_code}' -H "Host: $(grep -oP '^ALLOWED_HOSTS=\K[^,]+' .env)" -H 'X-Forwarded-Proto: https' http://127.0.0.1:8000/)
echo "health: HTTP $code"
[[ "$code" =~ ^(200|301|302)$ ]] || { sudo /usr/bin/systemctl status letmehelp-web letmehelp-worker letmehelp-beat --no-pager | tail -30; exit 1; }
echo "✅ deploy เสร็จ"

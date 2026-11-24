#!/usr/bin/env bash
# ติดตั้งเซิร์ฟเวอร์ครั้งแรก (Ubuntu 24.04+) — รันบน VPS:  sudo bash setup_server.sh โดเมน.com
# ทำซ้ำได้ปลอดภัย: ไม่ทับ .env / ฐานข้อมูลที่มีอยู่แล้ว
set -euo pipefail

DOMAIN="${1:?ใส่โดเมน เช่น: sudo bash setup_server.sh letmehelp.com}"
DEPLOYER="${SUDO_USER:?รันด้วย sudo จาก user ปกติ (ไม่ใช่ root ตรงๆ)}"
ROOT=/srv/letmehelp
APP=$ROOT/app
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "==> แพ็กเกจระบบ"
apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -y -q \
  python3 python3-venv python3-dev build-essential libpq-dev \
  postgresql redis-server nginx certbot python3-certbot-nginx \
  rsync ufw fail2ban unattended-upgrades

echo "==> swap 2GB (เครื่องไม่มี swap — กัน OOM ตอน pip/collectstatic)"
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q /swapfile /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "==> firewall: เปิดแค่ SSH + เว็บ"
SSH_PORT="$(echo "${SSH_CONNECTION:-x x x 22}" | awk '{print $4}')"
ufw allow "$SSH_PORT"/tcp
ufw allow 'Nginx Full'
ufw --force enable

echo "==> user สำหรับรันแอป (ไม่มีสิทธิ์ login) + โฟลเดอร์"
id letmehelp >/dev/null 2>&1 || useradd --system --home "$ROOT" --shell /usr/sbin/nologin letmehelp
mkdir -p "$APP"/{media,private_media,staticfiles}
chown "$DEPLOYER":"$DEPLOYER" "$ROOT" "$APP" "$APP/staticfiles"
chown letmehelp:letmehelp "$APP/media" "$APP/private_media"
chmod 750 "$APP/private_media"

echo "==> PostgreSQL"
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='letmehelp'" | grep -q 1; then
  DB_PASS="$(openssl rand -hex 24)"
  sudo -u postgres psql -q -c "CREATE ROLE letmehelp LOGIN PASSWORD '$DB_PASS'"
  sudo -u postgres createdb -O letmehelp letmehelp
else
  DB_PASS=""
fi

echo "==> .env (ค่าลับสร้างบนเครื่องนี้เท่านั้น ไม่ผ่านเครื่องอื่น)"
if [ ! -f "$APP/.env" ]; then
  [ -n "$DB_PASS" ] || { echo "มี DB role อยู่แล้วแต่ไม่มี .env — ตั้ง DATABASE_URL เองใน $APP/.env"; DB_PASS="SET_ME"; }
  cat > "$APP/.env" <<ENV
SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n/+=')
ALLOWED_HOSTS=$DOMAIN,www.$DOMAIN
CSRF_TRUSTED_ORIGINS=https://$DOMAIN,https://www.$DOMAIN
SITE_URL=https://$DOMAIN
DATABASE_URL=postgres://letmehelp:$DB_PASS@127.0.0.1:5432/letmehelp
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
DJANGO_ADMIN_ENABLED=False

# --- เติมเองด้วย: sudo nano $APP/.env  แล้ว  sudo systemctl restart letmehelp-web letmehelp-worker
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.hostinger.com
EMAIL_PORT=465
EMAIL_USE_SSL=True
EMAIL_HOST_USER=no-reply@$DOMAIN
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=Let Me Help <no-reply@$DOMAIN>
PROMPTPAY_ID=0939546499
PROMPTPAY_ACCOUNT_NAME=ศิตา วาริชวิวัฒน์
PROMPTPAY_BANK_ACCOUNT=4190084594
EASYSLIP_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_IDS=
ANTHROPIC_API_KEY=
LINE_CONTACT_URL=
ENV
fi
# root เขียน, แอปอ่านได้, คนอื่นอ่านไม่ได้
chown root:letmehelp "$APP/.env"
chmod 640 "$APP/.env"
# deployer ต้องอ่าน .env ได้ตอนรัน migrate/collectstatic
usermod -aG letmehelp "$DEPLOYER"
# อ่าน log ของบริการได้ (journalctl -u letmehelp-web) โดยไม่ต้อง sudo
usermod -aG systemd-journal "$DEPLOYER"

echo "==> systemd + nginx"
cp "$HERE"/systemd/letmehelp-*.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable letmehelp-web letmehelp-worker letmehelp-beat
sed "s/__DOMAIN__/$DOMAIN/g" "$HERE/nginx.conf" > /etc/nginx/sites-available/letmehelp
ln -sf /etc/nginx/sites-available/letmehelp /etc/nginx/sites-enabled/letmehelp
cp "$HERE/nginx-gzip.conf" /etc/nginx/conf.d/letmehelp-gzip.conf
cp "$HERE/nginx-catchall.conf" /etc/nginx/sites-available/letmehelp-catchall
ln -sf /etc/nginx/sites-available/letmehelp-catchall /etc/nginx/sites-enabled/letmehelp-catchall
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "==> ให้ deployer รีสตาร์ทบริการได้โดยไม่ต้องใส่รหัส (เฉพาะ 3 บริการนี้)"
cat > /etc/sudoers.d/letmehelp <<SUDO
$DEPLOYER ALL=(root) NOPASSWD: /usr/bin/systemctl restart letmehelp-web letmehelp-worker letmehelp-beat, /usr/bin/systemctl status letmehelp-web letmehelp-worker letmehelp-beat
SUDO
chmod 440 /etc/sudoers.d/letmehelp
visudo -cf /etc/sudoers.d/letmehelp

cat <<DONE

✅ ติดตั้งเสร็จ ขั้นต่อไป:
  1) จากเครื่อง Mac:  bash deploy/push.sh        (อัปโหลดโค้ด + migrate + start)
  2) บน VPS:          sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN --redirect
  3) บน VPS:          sudo nano $APP/.env        (ใส่ค่าอีเมล/PromptPay/คีย์ต่างๆ)
DONE

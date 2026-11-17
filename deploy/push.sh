#!/usr/bin/env bash
# รันบน Mac: bash deploy/push.sh   (ตั้ง Host "letmehelp-vps" ใน ~/.ssh/config หรือ VPS=user@ip bash deploy/push.sh)
# อัปโหลดเฉพาะโค้ด — ไม่ส่ง .env, ไฟล์ลูกค้า, สัญญา, ฐานข้อมูล หรือ venv ขึ้นเซิร์ฟเวอร์
set -euo pipefail
VPS="${VPS:-letmehelp-vps}"
cd "$(dirname "$0")/.."

# กันพลาด: deploy เฉพาะโค้ดที่ commit แล้ว และเทสผ่าน
[ -z "$(git status --porcelain)" ] || { echo "❌ มีไฟล์ยังไม่ commit — commit ก่อน deploy"; exit 1; }
.venv/bin/python manage.py test --parallel 1 -v 0

rsync -az --delete \
  --exclude '.git/' --exclude '.venv/' --exclude '.env' --exclude '.env.*' \
  --exclude '.seed_credentials' --exclude '*.pdf' --exclude '*.jpeg' \
  --exclude 'media/' --exclude 'private_media/' --exclude 'staticfiles/' \
  --exclude 'logs/' --exclude 'bootstrap-5.3.8-dist/' --exclude '.claude/' \
  --exclude '__pycache__/' --exclude '.DS_Store' \
  ./ "$VPS":/srv/letmehelp/app/

ssh "$VPS" 'bash /srv/letmehelp/app/deploy/remote_update.sh'

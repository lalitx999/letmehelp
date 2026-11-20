"""ตั้งค่า/ทดสอบบอท Telegram

  python manage.py telegram --find          หา chat id: แสดงแชท/กลุ่มที่เพิ่งคุยกับบอท
  python manage.py telegram --test          ส่งข้อความทดสอบไปทุก chat id ใน TELEGRAM_CHAT_IDS
  python manage.py telegram --test --chat -100123   ส่งทดสอบไป chat id ที่ระบุ (ยังไม่ต้องใส่ใน .env)

หา chat id ของกลุ่มไม่เจอ? เพิ่มบอทเข้ากลุ่ม แล้วพิมพ์ในกลุ่ม /start@ชื่อบอท (บอทในกลุ่มเห็นเฉพาะคำสั่ง
ถ้ายังเปิด privacy mode) จากนั้นรัน --find ภายใน 24 ชั่วโมง (Telegram เก็บ update ไว้แค่นั้น)
"""
import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.notifications.services import telegram_service


class Command(BaseCommand):
    help = "หา chat id และส่งข้อความทดสอบของบอท Telegram"

    def add_arguments(self, parser):
        parser.add_argument("--find", action="store_true", help="แสดง chat id จากข้อความล่าสุดที่บอทได้รับ")
        parser.add_argument("--test", action="store_true", help="ส่งข้อความทดสอบ")
        parser.add_argument("--chat", help="chat id ที่จะส่งทดสอบ (ค่าเริ่มต้น: TELEGRAM_CHAT_IDS)")

    def handle(self, *args, find, test, chat, **opts):
        if not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError("ยังไม่ได้ตั้ง TELEGRAM_BOT_TOKEN ใน .env")
        if not (find or test):
            find = True
        if find:
            self._find()
        if test:
            self._test(chat)

    def _api(self, method, **params):
        try:
            resp = requests.get(telegram_service.api_url(method), params=params, timeout=15)
        except requests.RequestException as exc:  # ไม่แสดง URL เพราะมี token
            raise CommandError(f"ติดต่อ Telegram ไม่ได้: {type(exc).__name__}") from None
        data = resp.json()
        if not data.get("ok"):
            raise CommandError(f"Telegram ตอบ: {data.get('description', resp.status_code)}")
        return data["result"]

    def _find(self):
        me = self._api("getMe")
        self.stdout.write(f"บอท: @{me['username']}  (ในกลุ่มที่ privacy mode เปิด: {'ใช่' if not me.get('can_read_all_group_messages') else 'ไม่'})")
        try:
            updates = self._api("getUpdates", allowed_updates='["message","my_chat_member","channel_post"]')
        except CommandError as exc:
            if "webhook" in str(exc).lower():
                raise CommandError("บอทนี้ตั้ง webhook ไว้ (อาจเคยใช้กับระบบอื่น) — getUpdates ใช้ไม่ได้ ต้องลบ webhook ก่อน") from None
            raise
        chats = {}
        for u in updates:
            msg = u.get("message") or u.get("channel_post") or u.get("my_chat_member") or {}
            c = msg.get("chat")
            if c:
                chats[c["id"]] = c
                if (msg.get("migrate_to_chat_id")):  # กลุ่มถูกอัปเกรดเป็น supergroup → id เปลี่ยน
                    chats[msg["migrate_to_chat_id"]] = {**c, "id": msg["migrate_to_chat_id"], "type": "supergroup"}
        if not chats:
            self.stdout.write(self.style.WARNING(
                "ยังไม่เห็นแชทไหนเลย — พิมพ์ /start@{} ในกลุ่ม (หรือทักบอทส่วนตัว) แล้วรันคำสั่งนี้อีกครั้ง".format(me["username"])
            ))
            return
        self.stdout.write("\nแชทที่พบ (ใส่ id ใน TELEGRAM_CHAT_IDS คั่นด้วยจุลภาค):")
        for c in chats.values():
            name = c.get("title") or " ".join(filter(None, [c.get("first_name"), c.get("last_name")])) or c.get("username", "")
            self.stdout.write(f"  {c['id']:>16}  {c['type']:<10}  {name}")

    def _test(self, chat):
        targets = [chat] if chat else settings.TELEGRAM_CHAT_IDS
        if not targets:
            raise CommandError("ยังไม่มี chat id — ใส่ TELEGRAM_CHAT_IDS ใน .env หรือระบุ --chat")
        now = timezone.localtime().strftime("%d/%m/%Y %H:%M")
        text = f"✅ ทดสอบแจ้งเตือนจาก Let Me Help\nบอทเชื่อมต่อกับเว็บเรียบร้อย ({now})"
        for chat_id in targets:
            ok = telegram_service.send_text(chat_id, text)
            style = self.style.SUCCESS if ok else self.style.ERROR
            self.stdout.write(style(f"{chat_id}: {'ส่งสำเร็จ' if ok else 'ส่งไม่สำเร็จ (ดู log — chat id ผิด หรือบอทไม่ได้อยู่ในกลุ่ม)'}"))

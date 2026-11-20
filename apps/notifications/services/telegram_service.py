"""แจ้งเตือนแอดมินผ่าน Telegram Bot (ฟรี ไม่จำกัดจำนวนข้อความ)
ตั้งค่า: สร้างบอทกับ @BotFather แล้วใส่ TELEGRAM_BOT_TOKEN · ให้แอดมินกด Start กับบอท แล้วใส่ chat id ใน TELEGRAM_CHAT_IDS"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)
API_BASE = "https://api.telegram.org/bot{token}/{method}"


def api_url(method: str) -> str:
    return API_BASE.format(token=settings.TELEGRAM_BOT_TOKEN, method=method)


class TelegramError(Exception):
    """ส่งไม่สำเร็จ (ไม่ใส่ URL ลงในข้อความ เพราะ URL มี token ของบอท)"""


def enabled() -> bool:
    return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_IDS)


def send_text(chat_id: str, text: str) -> bool:
    try:
        resp = requests.post(
            api_url("sendMessage"),
            json={"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": True},
            timeout=10,
        )
    except requests.RequestException as exc:
        raise TelegramError(type(exc).__name__) from None
    if resp.status_code == 429 or resp.status_code >= 500:
        raise TelegramError(f"HTTP {resp.status_code}")  # ลองใหม่ได้
    if resp.status_code != 200:  # เช่น 400/403: chat id ผิด หรือผู้ใช้ยังไม่ได้กด Start — ลองใหม่ก็ไม่หาย
        logger.warning("Telegram send failed chat=%s status=%s %s", chat_id, resp.status_code, resp.text[:150])
        return False
    return True


def push_to_admins(text: str) -> int:
    """ส่งหาทุก chat id ที่ตั้งไว้ คืนจำนวนที่ส่งสำเร็จ — ถ้ายังไม่ตั้งค่าก็ข้ามเงียบๆ"""
    if not enabled():
        return 0
    return sum(send_text(chat_id, text) for chat_id in settings.TELEGRAM_CHAT_IDS)


def send_photo(chat_id: str, photo: bytes, caption: str, filename: str = "slip.jpg") -> bool:
    """ส่งรูป (เช่น สลิป) พร้อมคำบรรยาย — คำบรรยายยาวได้ไม่เกิน 1024 ตัวอักษร"""
    try:
        resp = requests.post(
            api_url("sendPhoto"),
            data={"chat_id": chat_id, "caption": caption[:1024]},
            files={"photo": (filename, photo)},
            timeout=20,
        )
    except requests.RequestException as exc:
        raise TelegramError(type(exc).__name__) from None
    if resp.status_code == 429 or resp.status_code >= 500:
        raise TelegramError(f"HTTP {resp.status_code}")
    if resp.status_code != 200:  # เช่น รูปเสีย/ใหญ่เกิน → ให้ผู้เรียกส่งเป็นข้อความแทน
        logger.warning("Telegram photo failed chat=%s status=%s %s", chat_id, resp.status_code, resp.text[:150])
        return False
    return True


def push_photo_to_admins(photo: bytes, caption: str, filename: str = "slip.jpg") -> int:
    """ส่งรูปหาทุก chat id ถ้าส่งรูปไม่ผ่านจะส่งเป็นข้อความแทน (แอดมินยังได้รับแจ้งเตือน)"""
    if not enabled():
        return 0
    sent = 0
    for chat_id in settings.TELEGRAM_CHAT_IDS:
        ok = send_photo(chat_id, photo, caption, filename) if photo else False
        sent += ok or send_text(chat_id, caption)
    return sent


"""ตั้งค่าเว็บที่แก้ได้ในหลังบ้าน (เก็บใน SiteSetting) — ถ้าไม่ได้ตั้ง จะใช้ค่าจาก .env/settings เดิม
คีย์ลับ (EasySlip, LINE token, SMTP, Anthropic) ไม่เก็บในฐานข้อมูล ยังอยู่ใน .env"""
from django.conf import settings
from django.core.cache import cache

from apps.core.models import SiteSetting

CACHE_KEY = "site_settings:v1"
EDITABLE = (
    "PROMPTPAY_ID", "PROMPTPAY_ACCOUNT_NAME", "LINE_CONTACT_URL", "EXPIRY_REMINDER_DAYS", "ANNOUNCEMENT",
    "OWNER_NAME", "CONTACT_EMAIL", "SOCIAL_FACEBOOK", "SOCIAL_INSTAGRAM", "SOCIAL_YOUTUBE", "SOCIAL_TIKTOK", "SOCIAL_LEMON8",
)

# โซเชียลมีเดียที่แสดงใน Footer (ใส่ลิงก์ในหน้า ตั้งค่าเว็บ แล้วไอคอนจะโผล่เอง)
SOCIALS = (
    ("SOCIAL_FACEBOOK", "Facebook", "facebook"),
    ("SOCIAL_INSTAGRAM", "Instagram", "instagram"),
    ("SOCIAL_TIKTOK", "TikTok", "tiktok"),
    ("SOCIAL_LEMON8", "Lemon8", "lemon8"),
    ("SOCIAL_YOUTUBE", "YouTube", "youtube"),
)


def social_links() -> list[dict]:
    return [{"label": label, "icon": icon, "url": get(key)} for key, label, icon in SOCIALS if get(key)]


def _overrides() -> dict:
    data = cache.get(CACHE_KEY)
    if data is None:
        data = {s.key: s.value for s in SiteSetting.objects.filter(key__in=EDITABLE)}
        cache.set(CACHE_KEY, data, 300)
    return data


def get(key: str, default: str = "") -> str:
    value = _overrides().get(key, "")
    if value != "":
        return value
    fallback = getattr(settings, key, default)
    if isinstance(fallback, (list, tuple)):
        return ",".join(str(x) for x in fallback)
    return str(fallback) if fallback is not None else default


def reminder_days() -> list[int]:
    days = [int(x) for x in get("EXPIRY_REMINDER_DAYS").replace(" ", "").split(",") if x.isdigit() and int(x) > 0]
    return sorted(set(days), reverse=True) or [7, 3, 1]


def save_many(values: dict) -> None:
    """บันทึกหลายคีย์ด้วย upsert query เดียว (key เป็น unique) แทน update_or_create ทีละคีย์"""
    rows = [SiteSetting(key=key, value=values[key].strip()) for key in EDITABLE if key in values]
    if rows:
        SiteSetting.objects.bulk_create(rows, update_conflicts=True, unique_fields=["key"], update_fields=["value", "updated_at"])
    cache.delete(CACHE_KEY)


def secret_status() -> list[tuple[str, bool, str]]:
    """สถานะคีย์ลับ (ตั้งแล้ว/ยัง) — ไม่แสดงค่า"""
    return [
        ("EasySlip (ตรวจสลิปอัตโนมัติ)", bool(settings.EASYSLIP_API_KEY), "EASYSLIP_API_KEY"),
        ("Telegram Bot (แจ้งเตือนแอดมิน)", bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_IDS), "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_IDS"),
        ("อีเมล SMTP (แจ้งเตือนหมดอายุ/ยืนยันชำระเงิน)", "smtp" in settings.EMAIL_BACKEND.lower(), "EMAIL_BACKEND / EMAIL_HOST"),
        ("แชทบอท AI (Claude)", bool(settings.ANTHROPIC_API_KEY), "ANTHROPIC_API_KEY"),
    ]

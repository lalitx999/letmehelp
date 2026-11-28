"""Settings กลาง — ค่าลับทั้งหมดอ่านจาก .env (django-environ) ห้าม hardcode"""
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
SITE_URL = env("SITE_URL", default="http://localhost:8000")
SITE_NAME = "Let Me Help"
DJANGO_ADMIN_ENABLED = env.bool("DJANGO_ADMIN_ENABLED", default=False)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django_celery_beat",
    "apps.core",
    "apps.accounts",
    "apps.courses",
    "apps.enrollments",
    "apps.payments",
    "apps.learning",
    "apps.notifications",
    "apps.dashboard",
    "apps.chatbot",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
                "apps.core.context_processors.admin",
            ],
        },
    },
]

# PostgreSQL เป็นค่าตั้งต้น (ตั้ง DATABASE_URL ใน .env)
DATABASES = {"default": env.db("DATABASE_URL", default="postgres:///letmehelp")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "learning:my_courses"
LOGOUT_REDIRECT_URL = "core:home"

LANGUAGE_CODE = "th"
TIME_ZONE = "Asia/Bangkok"
USE_I18N = True
USE_TZ = True

# --- Static / Media -------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"  # ไฟล์สาธารณะ เช่น รูปปกคอร์ส
# ไฟล์ส่วนตัว (สลิป, PDF ประกอบการเรียน, รายงาน) ไม่เปิดผ่าน URL ตรง — เสิร์ฟผ่าน view ที่เช็กสิทธิ์
PRIVATE_MEDIA_ROOT = BASE_DIR / "private_media"

# --- Email ----------------------------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
# Hostinger: smtp.hostinger.com พอร์ต 465 + EMAIL_USE_SSL=True (หรือ 587 + EMAIL_USE_TLS=True) — เปิดได้อย่างใดอย่างหนึ่ง
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=not EMAIL_USE_SSL)
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=20)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Let Me Help <no-reply@letmehelp.local>")

# --- Celery ---------------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=CELERY_BROKER_URL)
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BEAT_SCHEDULE = {
    "expire-and-remind-enrollments": {
        "task": "apps.notifications.tasks.process_enrollment_expiry",
        "schedule": 60 * 60 * 6,  # ทุก 6 ชั่วโมง (ป้องกันซ้ำด้วย NotificationLog)
    },
}

# --- ธุรกิจ / บริการภายนอก --------------------------------------------------
# บัญชีรับเงิน (PromptPay) — ใช้สร้าง QR และตรวจชื่อ/เลขผู้รับในสลิป
PROMPTPAY_ID = env("PROMPTPAY_ID", default="")  # เบอร์โทร 0XXXXXXXXX หรือเลขบัตรประชาชน 13 หลัก
PROMPTPAY_ACCOUNT_NAME = env("PROMPTPAY_ACCOUNT_NAME", default="")
PROMPTPAY_BANK_ACCOUNT = env("PROMPTPAY_BANK_ACCOUNT", default="")  # เลขบัญชีที่ผูกพร้อมเพย์ ใช้เทียบผู้รับในสลิป
# EasySlip — ถ้าไม่ตั้ง key ระบบจะส่งสลิปเข้าคิว "ตรวจด้วยมือ" แทน
EASYSLIP_API_KEY = env("EASYSLIP_API_KEY", default="")
EASYSLIP_API_URL = env("EASYSLIP_API_URL", default="https://api.easyslip.com/v2/verify/bank")
# Telegram Bot — แจ้งเตือนแอดมิน (สมัครใหม่ / ส่งสลิป / ชำระแล้ว) ฟรีไม่จำกัดข้อความ
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_CHAT_IDS = env.list("TELEGRAM_CHAT_IDS", default=[])
# แจ้งเตือนก่อนหมดอายุ (วัน) — คอร์สอายุ 1 ปี เตือนล่วงหน้า 30 วันเพื่อชวนต่ออายุ
EXPIRY_REMINDER_DAYS = [30, 7, 1]
# ถอยวิดีโอเมื่อกลับมาเรียนต่อ (วินาที)
RESUME_REWIND_SECONDS = 10
# ฟอนต์ไทยสำหรับ PDF — ใช้ Sarabun (OFL) ที่มากับโปรเจกต์ เปลี่ยนได้ผ่าน .env
PDF_FONT_PATH = env("PDF_FONT_PATH", default=str(BASE_DIR / "static" / "fonts" / "Sarabun-Regular.ttf"))

# แชทบอท: ถ้าไม่ตั้ง ANTHROPIC_API_KEY จะใช้บอทกติกา (ตอบจากข้อมูลจริงในระบบ ไม่เสียค่าใช้จ่าย)
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
CHATBOT_MODEL = env("CHATBOT_MODEL", default="claude-opus-5-5")
CHATBOT_EFFORT = env("CHATBOT_EFFORT", default="low")  # low | medium | high
CHATBOT_FALLBACK_MODEL = env("CHATBOT_FALLBACK_MODEL", default="claude-opus-4-8")  # เว้นว่างเพื่อปิดโมเดลสำรอง
# ลิงก์ LINE ส่วนตัวของเจ้าของ (https://line.me/ti/p/...) — ปุ่มทักถามก่อนสมัคร ในหน้าคอร์ส แดชบอร์ดนักเรียน และแชทบอท
LINE_CONTACT_URL = env("LINE_CONTACT_URL", default="") or "https://line.me/ti/p/uzCrWzXaGX"

# โซเชียลมีเดียของแบรนด์ (ลิงก์สาธารณะ ไม่ใช่ความลับ) — ตั้งค่าตั้งต้นไว้ที่นี่ ให้แอดมินแก้ทับได้ที่หลังบ้าน → ตั้งค่าเว็บ
# `or` = ถ้าใน .env มีคีย์แต่เว้นว่าง ก็ยังใช้ลิงก์ของแบรนด์ (ลิงก์ไม่มี tracking param)
SOCIAL_TIKTOK = env("SOCIAL_TIKTOK", default="") or "https://www.tiktok.com/@letmehelp.eng"
SOCIAL_FACEBOOK = env("SOCIAL_FACEBOOK", default="") or "https://www.facebook.com/profile.php?id=61590751587536"
SOCIAL_INSTAGRAM = env("SOCIAL_INSTAGRAM", default="") or "https://www.instagram.com/letmehelp.eng/"
SOCIAL_LEMON8 = env("SOCIAL_LEMON8", default="") or "https://s.lemon8-app.com/s/GgQwRbkmFy"
SOCIAL_YOUTUBE = env("SOCIAL_YOUTUBE", default="") or "https://www.youtube.com/@letmehelp.eng4848"

SESSION_COOKIE_AGE = 60 * 60 * 24 * 30

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"std": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "std"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

# ให้ Django messages ใช้ class ของ Bootstrap
from django.contrib.messages import constants as _m  # noqa: E402

MESSAGE_TAGS = {_m.DEBUG: "secondary", _m.INFO: "info", _m.SUCCESS: "success", _m.WARNING: "warning", _m.ERROR: "danger"}
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24 * 7  # ลิงก์ตั้ง/ลืมรหัสผ่านใช้ได้ 7 วัน (นักเรียนที่นำเข้าอาจเปิดอีเมลช้า)

# YouTube (embed) ต้องรู้ว่าเว็บไหนฝังวิดีโอ ไม่งั้นขึ้น "Error 153 Video player configuration error"
# (เจอบนแอปที่ติดตั้งบน iPad) ค่าตั้งต้นของ Django คือ same-origin = ไม่ส่ง Referer ข้ามโดเมนเลย
# strict-origin-when-cross-origin: ข้ามโดเมนส่งแค่ชื่อโดเมน (ไม่ส่ง path ของหน้า) · ในเว็บเดียวกันส่งเต็ม
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

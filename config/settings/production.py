from .base import *  # noqa: F401,F403

DEBUG = False  # ห้ามเปิดใน production
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")  # noqa: F405  (บังคับตั้งค่า)

# WhiteNoise เสิร์ฟ static (หรือให้ Nginx เสิร์ฟ /static/ และ /media/ โดยตรง)
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)  # noqa: F405
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])  # noqa: F405
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# ไม่เข้า HSTS preload list โดยเจตนา (ถอนออกยากหลายเดือน) — เปิดได้ภายหลังเมื่อ HTTPS เสถียรแล้ว
SILENCED_SYSTEM_CHECKS = ["security.W021"]

# รันแบบ ASGI: การเชื่อมต่อ DB ค้างข้าม request (CONN_MAX_AGE>0) จะรั่วตามเธรดของ async view
# จนช่องเชื่อมต่อ PostgreSQL เต็ม → 500 ทั้งเว็บ จึงปิดและเปิด-ปิดต่อ request แทน (ตามคำแนะนำของ Django สำหรับ ASGI)
DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405

from .base import *  # noqa: F401,F403

DEBUG = True
DJANGO_ADMIN_ENABLED = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

# ไม่ต้องมี Redis ตอนพัฒนา: รัน Celery task แบบ eager (ยังเรียกผ่าน .delay() เหมือน production)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = False

MIDDLEWARE.insert(0, "apps.core.middleware.NoCacheStaticMiddleware")

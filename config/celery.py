import os

from celery import Celery

# ค่าเริ่มต้นเป็น production เหมือน wsgi/asgi: worker ที่ลืมตั้ง env จะไม่รันด้วย DEBUG=True / eager
# ตอนพัฒนาไม่ต้องรัน worker (local ใช้ CELERY_TASK_ALWAYS_EAGER)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

app = Celery("letmehelp")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

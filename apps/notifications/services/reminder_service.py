"""ส่งอีเมลเตือนต่ออายุตามที่แอดมินเลือก — เข้าคิว Celery ทั้งหมด ไม่ส่งอีเมลใน request"""
from django.utils import timezone

from apps.enrollments.models import Enrollment
from apps.notifications.tasks import send_expiry_email


def queue_expiry_reminders(enrollment_ids) -> int:
    """คืนจำนวนที่เข้าคิวจริง (นับเฉพาะ id ที่มีอยู่) — query เดียว ไม่ดึงทีละแถว"""
    now = timezone.now()
    rows = list(Enrollment.objects.filter(pk__in=enrollment_ids).values_list("pk", "expires_at"))
    for pk, expires_at in rows:
        send_expiry_email.delay(pk, max((expires_at - now).days, 0))
    return len(rows)

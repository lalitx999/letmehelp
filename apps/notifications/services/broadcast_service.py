"""ส่งอีเมลประกาศถึงนักเรียน (แอดมินสั่งจากหลังบ้าน) — เลือกกลุ่มผู้รับ แล้วส่งเป็นชุดใน Celery ไม่ค้าง request"""
from django.conf import settings
from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.accounts.models import User
from apps.core.exceptions import ActionError
from apps.core.services import audit_service
from apps.enrollments.models import Enrollment

BATCH = 40  # อีเมลต่อ 1 งาน (ใช้การเชื่อมต่อ SMTP เดียวกันทั้งชุด)


def _active_enrollments():
    return Enrollment.objects.filter(status=Enrollment.Status.ACTIVE, expires_at__gt=timezone.now())


def targets():
    """[(ค่า, ชื่อกลุ่ม, จำนวนผู้รับ)] สำหรับตัวเลือกในฟอร์ม"""
    from apps.courses.models import Course

    out = [
        ("active", "นักเรียนที่กำลังเรียนอยู่ (ทุกคอร์ส)", recipients("active").count()),
        ("expired", "นักเรียนที่สิทธิ์หมดแล้ว (ยังไม่ต่ออายุ)", recipients("expired").count()),
        ("all", "บัญชีนักเรียนทั้งหมด", recipients("all").count()),
    ]
    for c in Course.objects.only("id", "title").order_by("title"):
        out.append((f"course:{c.pk}", f"กำลังเรียน {c.title}", recipients(f"course:{c.pk}").count()))
    return out


def recipients(target: str):
    qs = User.objects.filter(is_staff=False, is_active=True)
    active = _active_enrollments().filter(user=OuterRef("pk"))
    if target == "all":
        return qs
    if target == "active":
        return qs.filter(Exists(active))
    if target == "expired":
        return qs.filter(Exists(Enrollment.objects.filter(user=OuterRef("pk")))).exclude(Exists(active))
    if target.startswith("course:") and target[7:].isdigit():
        return qs.filter(Exists(active.filter(course_id=int(target[7:]))))
    raise ActionError("กลุ่มผู้รับไม่ถูกต้อง")


def render_body(name: str, message: str) -> str:
    return (
        f"สวัสดีค่ะ คุณ{name}\n\n{message.strip()}\n\n"
        f"—\n{settings.SITE_NAME} — มานี่เดี๋ยวพี่สอน\n{settings.SITE_URL}\n"
        f"(คุณได้รับอีเมลนี้เพราะมีบัญชีนักเรียนกับ {settings.SITE_NAME})"
    )


def send_test(user, subject: str, message: str) -> str:
    from apps.notifications.tasks import send_broadcast_batch

    send_broadcast_batch.delay([user.pk], f"[ทดสอบ] {subject}", message, include_staff=True)
    return f"ส่งอีเมลทดสอบไปที่ {user.email} แล้ว"


def send(target: str, subject: str, message: str, request) -> int:
    from apps.notifications.tasks import send_broadcast_batch

    ids = list(recipients(target).values_list("pk", flat=True))
    if not ids:
        raise ActionError("ไม่มีผู้รับในกลุ่มนี้")
    for i in range(0, len(ids), BATCH):
        send_broadcast_batch.delay(ids[i:i + BATCH], subject, message)
    audit_service.log(request=request, action="broadcast", model="Email", label=subject[:200],
                      changes={"target": target, "recipients": len(ids)})
    return len(ids)

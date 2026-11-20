import logging

from celery import shared_task
from django.utils import timezone

from apps.enrollments.selectors.enrollment_selector import expiring_enrollments
from apps.enrollments.services.enrollment_service import expire_overdue

from .models import NotificationLog
from .services import email_service, telegram_service

logger = logging.getLogger(__name__)


@shared_task(autoretry_for=(telegram_service.TelegramError,), retry_backoff=True, max_retries=3)
def notify_admins(text: str):
    return telegram_service.push_to_admins(text)


@shared_task(autoretry_for=(telegram_service.TelegramError,), retry_backoff=True, max_retries=3)
def notify_slip_submitted(slip_id: int):
    """แจ้งแอดมินว่ามีสลิปใหม่: ส่งรูปสลิป + รายละเอียดออเดอร์ + ลิงก์ไปหน้าตรวจสลิป"""
    if not telegram_service.enabled():
        return 0
    import os

    from django.conf import settings
    from django.urls import reverse

    from apps.payments.models import PaymentSlip

    slip = PaymentSlip.objects.select_related("order__user", "order__course").get(pk=slip_id)
    order, user = slip.order, slip.order.user
    package = order.package_label or (f"{order.duration_days} วัน" if order.duration_days else "")
    lines = [
        f"🧾 สลิปใหม่ · ออเดอร์ #{order.pk}" + (" (ต่ออายุ)" if order.is_renewal else ""),
        f"👤 {user.full_name}",
        f"📧 {user.email}",
        f"📞 {user.phone}",
        f"📚 {order.course.title}" + (f" · {package}" if package else ""),
        f"💰 ยอดที่ต้องชำระ: ฿{order.amount:,.2f}",
        f"⏰ {timezone.localtime(slip.created_at):%d/%m/%Y %H:%M}",
        "",
        "ระบบกำลังตรวจสลิปอัตโนมัติ จะแจ้งผลอีกครั้ง",
        f"🔗 ตรวจสลิปในหลังบ้าน: {settings.SITE_URL}{reverse('dashboard:slip_list')}",
    ]
    try:
        with slip.image.open("rb") as fh:
            photo = fh.read()
    except OSError:
        photo = b""
    return telegram_service.push_photo_to_admins(photo, "\n".join(lines), os.path.basename(slip.image.name) or "slip.jpg")


@shared_task(autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def send_payment_success_email(order_id: int):
    from apps.enrollments.models import Enrollment
    from apps.payments.models import Order

    order = Order.objects.select_related("user", "course").only(
        "id", "user__email", "user__full_name", "course__id", "course__title", "user_id"
    ).get(pk=order_id)
    expires = Enrollment.objects.filter(user_id=order.user_id, course_id=order.course.id).values_list(
        "expires_at", flat=True
    ).first()
    if expires:
        email_service.send_payment_success(
            email=order.user.email, name=order.user.full_name, course_title=order.course.title, expires_at=expires
        )


@shared_task
def process_enrollment_expiry():
    """รันเป็นรอบ (Celery beat): ปิดสิทธิ์ที่หมดอายุ (bulk) + ส่งอีเมลเตือนล่วงหน้า"""
    expired = expire_overdue()
    sent = 0
    from apps.core.services import settings_service

    for days in settings_service.reminder_days():
        kind = f"expiry_{days}d"
        candidates = list(expiring_enrollments(days))
        if not candidates:
            continue
        # คัดคนที่เคยเตือนรอบนี้แล้วออกด้วย query เดียว แล้วบันทึก log แบบ bulk
        # (ignore_conflicts + unique constraint กันซ้ำอีกชั้น — beat รันทีละรอบอยู่แล้ว)
        already = set(
            NotificationLog.objects.filter(kind=kind, enrollment__in=candidates).values_list("enrollment_id", "expires_at_snapshot")
        )
        fresh = [e for e in candidates if (e.pk, e.expires_at) not in already]
        NotificationLog.objects.bulk_create(
            [NotificationLog(enrollment=e, kind=kind, expires_at_snapshot=e.expires_at) for e in fresh], ignore_conflicts=True
        )
        for enr in fresh:
            send_expiry_email.delay(enr.pk, days)
        sent += len(fresh)
    return {"expired": expired, "reminders_queued": sent}


@shared_task(autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def send_expiry_email(enrollment_id: int, days_left: int):
    from apps.enrollments.models import Enrollment

    enr = Enrollment.objects.select_related("user", "course").only(
        "id", "expires_at", "user__email", "user__full_name", "course__title", "course__slug"
    ).get(pk=enrollment_id)
    email_service.send_expiry_reminder(
        email=enr.user.email,
        name=enr.user.full_name,
        course_title=enr.course.title,
        course_slug=enr.course.slug,
        expires_at=timezone.localtime(enr.expires_at),
        days_left=days_left,
    )

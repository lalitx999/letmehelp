import logging

from celery import shared_task
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.enrollments.selectors.enrollment_selector import expiring_enrollments
from apps.enrollments.services.enrollment_service import expire_overdue

from .models import NotificationLog
from .services import email_service, telegram_service

logger = logging.getLogger(__name__)


@shared_task(autoretry_for=(telegram_service.TelegramError,), retry_backoff=True, max_retries=3)
def notify_admins(text: str):
    return telegram_service.push_to_admins(text)


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
        for enr in expiring_enrollments(days):
            kind = f"expiry_{days}d"
            try:
                with transaction.atomic():
                    NotificationLog.objects.create(enrollment=enr, kind=kind, expires_at_snapshot=enr.expires_at)
            except IntegrityError:
                continue  # เคยส่งแล้ว
            send_expiry_email.delay(enr.pk, days)
            sent += 1
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

from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.accounts.models import User
from apps.enrollments.models import Enrollment
from apps.payments.models import PaymentSlip
from apps.payments.selectors import payment_selector


def overview(days=30):
    since = timezone.now() - timedelta(days=days)
    sales = payment_selector.sales_summary(date_from=timezone.localdate() - timedelta(days=days - 1))
    signups = (
        User.objects.filter(is_staff=False, date_joined__gte=since)
        .annotate(day=TruncDate("date_joined"))
        .values("day")
        .annotate(n=Count("id"))
        .order_by("day")
    )
    return {
        "days": days,
        "revenue": sales["revenue"],
        "paid_orders": sales["orders"],
        "students_total": User.objects.filter(is_staff=False).count(),
        "signups_period": sum(r["n"] for r in signups),
        "active_enrollments": Enrollment.objects.filter(status=Enrollment.Status.ACTIVE).count(),
        "pending_slips": PaymentSlip.objects.filter(status=PaymentSlip.Status.MANUAL_REVIEW).count(),
        "expiring_7d": Enrollment.objects.filter(status=Enrollment.Status.ACTIVE, expires_at__gt=timezone.now(), expires_at__lte=timezone.now() + timedelta(days=7)).count(),
        "reviewing_orders": __import__("apps.payments.models", fromlist=["Order"]).Order.objects.filter(status="reviewing").count(),
        "new_students_7d": User.objects.filter(is_staff=False, date_joined__gte=timezone.now() - timedelta(days=7)).count(),
        "recent_activity": list(__import__("apps.core.models", fromlist=["AuditLog"]).AuditLog.objects.select_related("user").only("id", "action", "model", "object_repr", "actor_label", "created_at", "user__full_name")[:8]),
        "daily_sales": payment_selector.daily_sales(days),
        "by_course": payment_selector.sales_by_course(date_from=timezone.localdate() - timedelta(days=days - 1)),
    }


def students_list(search=""):
    qs = (
        User.objects.filter(is_staff=False)
        .only("id", "full_name", "email", "phone", "date_joined", "last_login", "is_active")
        .annotate(course_count=Count("enrollments"))
    )
    if search:
        from django.db.models import Q

        qs = qs.filter(Q(full_name__icontains=search) | Q(email__icontains=search) | Q(phone__icontains=search))
    return qs


def students_for_export(date_from=None, date_to=None):
    qs = (
        Enrollment.objects.select_related("user", "course")
        .values_list(
            "user__full_name", "user__email", "user__phone", "course__title",
            "started_at", "expires_at", "status",
        )
        .order_by("-started_at")
    )
    if date_from:
        qs = qs.filter(started_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(started_at__date__lte=date_to)
    return qs


def enrollments_by_expiry(flt="soon"):
    """รายการสิทธิ์เรียนเรียงตามวันหมดอายุ: soon=ภายใน 30 วัน, expired=หมดอายุแล้ว, active=ทั้งหมดที่ยังเรียนอยู่"""
    from datetime import timedelta

    from django.utils import timezone

    now = timezone.now()
    qs = Enrollment.objects.select_related("user", "course").only(
        "id", "status", "expires_at", "user__full_name", "user__email", "user__phone", "course__title"
    )
    if flt == "expired":
        return qs.filter(expires_at__lte=now).order_by("-expires_at")
    qs = qs.filter(expires_at__gt=now)
    if flt == "soon":
        qs = qs.filter(expires_at__lte=now + timedelta(days=30))
    return qs.order_by("expires_at")

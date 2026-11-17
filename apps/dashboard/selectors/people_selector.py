from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.accounts.models import User
from apps.enrollments.models import Enrollment
from apps.payments.models import Order


def students_qs():
    now = timezone.now()
    return (
        User.objects.filter(is_staff=False)
        .only("id", "full_name", "email", "phone", "date_joined", "last_login", "is_active")
        .annotate(
            course_count=Count("enrollments", distinct=True),
            active_count=Count("enrollments", filter=Q(enrollments__status="active", enrollments__expires_at__gt=now), distinct=True),
        )
    )


def student_enrollment_filter(qs, value):
    """กรองนักเรียนตามสถานะการเรียน: active=กำลังเรียน · expired=มีแต่หมดแล้ว · none=ยังไม่เคยซื้อ"""
    if value == "active":
        return qs.filter(active_count__gt=0)
    if value == "expired":
        return qs.filter(active_count=0, course_count__gt=0)
    if value == "none":
        return qs.filter(course_count=0)
    return qs


def student_enrollments(user):
    return list(Enrollment.objects.filter(user=user).select_related("course").order_by("-expires_at"))


def student_orders(user, limit=15):
    return list(Order.objects.filter(user=user).select_related("course").order_by("-created_at")[:limit])


def enrollments_qs():
    return Enrollment.objects.select_related("user", "course").only(
        "id", "status", "source", "note", "expires_at", "started_at",
        "user__id", "user__full_name", "user__email", "user__phone", "course__id", "course__title",
    )


def enrollment_tab_filter(qs, value):
    now = timezone.now()
    if value == "soon":
        return qs.filter(status="active", expires_at__gt=now, expires_at__lte=now + timedelta(days=30))
    if value == "expired":
        return qs.filter(Q(status="expired") | Q(status="active", expires_at__lte=now))
    if value == "active":
        return qs.filter(status="active", expires_at__gt=now)
    if value == "cancelled":
        return qs.filter(status="cancelled")
    return qs

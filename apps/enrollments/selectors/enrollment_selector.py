from django.utils import timezone

from apps.enrollments.models import Enrollment


def get_active_enrollment(user, course_id):
    """คืน enrollment ที่ยังไม่หมดอายุของ user ในคอร์สนี้ (หรือ None)"""
    return (
        Enrollment.objects.filter(
            user=user, course_id=course_id, status=Enrollment.Status.ACTIVE, expires_at__gt=timezone.now()
        )
        .only("id", "expires_at", "course_id")
        .first()
    )


def get_enrollment(user, course_id):
    return Enrollment.objects.filter(user=user, course_id=course_id).only("id", "status", "expires_at").first()


def user_enrollments(user):
    return list(
        Enrollment.objects.filter(user=user)
        .select_related("course", "course__category")
        .only(
            "id", "status", "started_at", "expires_at",
            "course__id", "course__title", "course__slug", "course__thumbnail", "course__cover_url", "course__category__name", "course__category__slug",
        )
        .order_by("-expires_at")
    )


def expiring_enrollments(days_ahead: int):
    """enrollment ที่จะหมดอายุภายใน N วัน (ช่วง [N-1, N] วัน)"""
    now = timezone.now()
    from datetime import timedelta

    return (
        Enrollment.objects.filter(
            status=Enrollment.Status.ACTIVE,
            expires_at__gt=now + timedelta(days=days_ahead - 1),
            expires_at__lte=now + timedelta(days=days_ahead),
        )
        .select_related("user", "course")
        .only("id", "expires_at", "user__email", "user__full_name", "course__title", "course__slug")
    )

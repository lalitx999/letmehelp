from django.conf import settings
from django.db import models


class Enrollment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "กำลังเรียน"
        EXPIRED = "expired", "หมดอายุ"
        CANCELLED = "cancelled", "ยกเลิก"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments")
    course = models.ForeignKey("courses.Course", on_delete=models.PROTECT, related_name="enrollments")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    source = models.CharField(
        max_length=10, default="purchase", choices=[("purchase", "ซื้อ"), ("manual", "แอดมินมอบ"), ("comp", "แถม/ทดลอง")]
    )
    note = models.CharField(max_length=300, blank=True)
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    started_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # 1 คน 1 คอร์ส 1 แถว — ต่ออายุโดยเลื่อน expires_at
        constraints = [models.UniqueConstraint(fields=["user", "course"], name="uniq_enrollment_user_course")]
        indexes = [models.Index(fields=["status", "expires_at"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id}:{self.course_id}"

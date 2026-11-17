from django.db import models


class NotificationLog(models.Model):
    """กันส่งแจ้งเตือนซ้ำ: 1 enrollment ต่อ 1 ประเภท (เช่น expiry_7d) ส่งได้ครั้งเดียวต่อรอบการต่ออายุ"""

    enrollment = models.ForeignKey("enrollments.Enrollment", on_delete=models.CASCADE, related_name="+")
    kind = models.CharField(max_length=30)
    expires_at_snapshot = models.DateTimeField()  # ต่ออายุแล้ว expires_at เปลี่ยน → ส่งรอบใหม่ได้
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "kind", "expires_at_snapshot"], name="uniq_notification_once"
            )
        ]

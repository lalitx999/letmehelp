from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.storage import private_storage


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "รอชำระเงิน"
        REVIEWING = "reviewing", "กำลังตรวจสลิป"
        PAID = "paid", "ชำระแล้ว"
        REJECTED = "rejected", "ไม่ผ่าน"
        CANCELLED = "cancelled", "ยกเลิก"
        REFUNDED = "refunded", "คืนเงิน"

    class Source(models.TextChoices):
        ONLINE = "online", "สั่งซื้อเอง"
        MANUAL = "manual", "แอดมินสร้าง"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    course = models.ForeignKey("courses.Course", on_delete=models.PROTECT, related_name="orders")
    amount = models.DecimalField(max_digits=9, decimal_places=2)  # snapshot ราคา ณ ตอนสั่งซื้อ
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    is_renewal = models.BooleanField(default=False)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.ONLINE)
    note = models.CharField(max_length=300, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    duration_days = models.PositiveIntegerField(default=0)  # snapshot อายุของแพ็กเกจที่เลือก
    package_label = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["paid_at"]),
        ]

    def __str__(self):
        return f"Order#{self.pk}"


def slip_path(instance, filename):
    return f"slips/{instance.order_id}/{filename}"


class PaymentSlip(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "รอตรวจ"
        VERIFIED = "verified", "ผ่าน"
        MANUAL_REVIEW = "manual_review", "รอแอดมินตรวจ"
        REJECTED = "rejected", "ไม่ผ่าน"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="slips")
    image = models.ImageField(upload_to=slip_path, storage=private_storage)
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.PENDING)
    reason = models.CharField(max_length=255, blank=True)
    trans_ref = models.CharField(max_length=64, null=True, blank=True)  # เลขอ้างอิงธนาคาร กันสลิปซ้ำ
    verified_amount = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    raw_response = models.JSONField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # สลิปใบเดียวใช้ได้ครั้งเดียว (DB บังคับ ป้องกัน race condition)
            models.UniqueConstraint(
                fields=["trans_ref"], condition=Q(trans_ref__isnull=False), name="uniq_slip_trans_ref"
            )
        ]
        indexes = [models.Index(fields=["status", "-created_at"])]

    def __str__(self):
        return f"Slip#{self.pk} ({self.status})"

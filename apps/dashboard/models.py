from django.conf import settings
from django.db import models

from apps.core.storage import private_storage


class ReportExport(models.Model):
    """งานสร้างรายงาน PDF/Excel — สร้างเบื้องหลังด้วย Celery แล้วให้ดาวน์โหลดเมื่อเสร็จ"""

    class Kind(models.TextChoices):
        SALES = "sales", "ยอดขาย"
        STUDENTS = "students", "รายชื่อนักเรียน/การสมัครเรียน"
        ORDERS = "orders", "ออเดอร์ทั้งหมด"
        EXPIRING = "expiring", "สิทธิ์ที่ใกล้หมดอายุ (30 วัน)"

    class Format(models.TextChoices):
        XLSX = "xlsx", "Excel"
        PDF = "pdf", "PDF"

    class Status(models.TextChoices):
        PENDING = "pending", "กำลังสร้าง"
        DONE = "done", "เสร็จแล้ว"
        FAILED = "failed", "ล้มเหลว"

    kind = models.CharField(max_length=10, choices=Kind.choices)
    fmt = models.CharField(max_length=5, choices=Format.choices)
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    file = models.FileField(upload_to="exports/", storage=private_storage, blank=True)
    error = models.CharField(max_length=255, blank=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

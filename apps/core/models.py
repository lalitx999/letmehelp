from django.conf import settings
from django.db import models
from django.utils import timezone


# ---- Soft delete (ถังขยะ) ---------------------------------------------------
class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        return self.filter(deleted_at__isnull=False)


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """manager หลัก: ซ่อนรายการที่อยู่ในถังขยะ จึงไม่โผล่บนเว็บสาธารณะ/ตัวเลือกต่างๆ โดยอัตโนมัติ"""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class SoftDeleteModel(models.Model):
    """ลบ = ใส่ deleted_at (กู้คืนได้) · หลังบ้านใช้ `all_objects` เพื่อเห็นรายการในถังขยะ"""

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = SoftDeleteManager()  # ต้องประกาศก่อน เพื่อให้เป็น default manager (ใช้กับ reverse relation)
    all_objects = models.Manager.from_queryset(SoftDeleteQuerySet)()

    class Meta:
        abstract = True

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])


# ---- ประวัติการแก้ไข -----------------------------------------------------------
class AuditLog(models.Model):
    """ใครทำอะไรกับข้อมูลไหนเมื่อไหร่ — เขียนจาก service (ไม่ใช้ signal เพื่อให้รู้ตัวผู้ทำ)"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    actor_label = models.CharField(max_length=120, blank=True)  # เช่น "ระบบ (EasySlip)" เมื่อไม่มีผู้ใช้
    action = models.CharField(max_length=30, db_index=True)
    model = models.CharField(max_length=60, db_index=True)
    object_id = models.CharField(max_length=40, blank=True)
    object_repr = models.CharField(max_length=200, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["model", "object_id"])]


# ---- ตั้งค่าเว็บที่แก้ได้ในหลังบ้าน (override ค่าจาก .env) ----------------------------
class SiteSetting(models.Model):
    key = models.CharField(max_length=60, unique=True)
    value = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key

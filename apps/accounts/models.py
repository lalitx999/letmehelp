from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import RegexValidator
from django.db import models

phone_validator = RegexValidator(r"^0\d{8,9}$", "เบอร์โทรไม่ถูกต้อง (เช่น 0812345678)")


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("ต้องระบุอีเมล")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    """ล็อกอินด้วยอีเมล เก็บชื่อ-เบอร์โทรตามที่ลูกค้าต้องการ"""

    username = None
    first_name = None
    last_name = None
    email = models.EmailField("อีเมล", unique=True)
    full_name = models.CharField("ชื่อ-นามสกุล", max_length=150)
    phone = models.CharField("เบอร์โทร", max_length=10, validators=[phone_validator])
    line_user_id = models.CharField(max_length=64, blank=True)
    terms_accepted_at = models.DateTimeField("ยอมรับข้อกำหนด/นโยบายเมื่อ", null=True, blank=True)
    admin_note = models.TextField("โน้ตแอดมิน", blank=True)  # บันทึกภายใน นักเรียนมองไม่เห็น

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name", "phone"]
    objects = UserManager()

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return self.full_name or self.email

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name.split(" ")[0] if self.full_name else self.email

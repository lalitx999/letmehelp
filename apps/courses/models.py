from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.core.models import SoftDeleteModel
from apps.core.storage import private_storage


class Category(SoftDeleteModel):
    """หมวดคอร์ส เช่น TGAT, A-Level (อนาคต: Grammar, Vocab, Conversation, Reading, เข้า ม.4)"""

    name = models.CharField("ชื่อหมวด", max_length=80)
    slug = models.SlugField(unique=True, allow_unicode=True)
    description = models.CharField(max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)


class Course(SoftDeleteModel):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="courses")
    title = models.CharField("ชื่อคอร์ส", max_length=160)
    slug = models.SlugField(unique=True, allow_unicode=True, max_length=180)
    subtitle = models.CharField("คำโปรย", max_length=220, blank=True)
    description = models.TextField("รายละเอียด", blank=True)
    thumbnail = models.ImageField("รูปปก (อัปโหลด)", upload_to="courses/", blank=True)
    # ลิงก์รูปปกจากภายนอก (https://...) หรือไฟล์ในเว็บ (/static/...) — ใช้เมื่อไม่ได้อัปโหลดรูป
    cover_url = models.CharField("ลิงก์รูปปก", max_length=500, blank=True)
    price = models.DecimalField("ราคา (บาท)", max_digits=9, decimal_places=2)
    access_days = models.PositiveIntegerField("อายุคอร์ส (วัน)", default=365)
    # ราคาโปรโมชัน: ใช้ได้ถึงสิ้นวัน promo_ends_on (เวลาไทย) แล้วกลับเป็นราคาปกติเอง
    promo_price = models.DecimalField("ราคาโปรโมชัน (บาท)", max_digits=9, decimal_places=2, null=True, blank=True)
    promo_ends_on = models.DateField("โปรโมชันถึงวันที่", null=True, blank=True)
    # หนังสือเล่มจริงขายผ่านร้านภายนอก เช่น Shopee
    book_url = models.URLField("ลิงก์ซื้อหนังสือเล่ม (Shopee)", max_length=500, blank=True)
    is_published = models.BooleanField("เผยแพร่", default=False)
    is_featured = models.BooleanField("แนะนำหน้าแรก", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["is_published", "-created_at"])]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("courses:detail", kwargs={"slug": self.slug})

    @property
    def promo_active(self) -> bool:
        return self.promo_price is not None and self.promo_ends_on is not None and self.promo_ends_on >= timezone.localdate()

    @property
    def current_price(self):
        """ราคาที่ขายจริงตอนนี้ (โปรโมชันถ้ายังไม่หมดเขต)"""
        return self.promo_price if self.promo_active else self.price

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title, allow_unicode=True)
        super().save(*args, **kwargs)


class CoursePackage(models.Model):
    """แพ็กเกจราคาเพิ่มเติมของคอร์ส (เช่น 6 เดือน / 1 ปี / ตลอดชีพ)
    แพ็กเกจหลักคือ Course.price + Course.access_days — แพ็กเกจเหล่านี้เป็นตัวเลือกเสริม"""

    LIFETIME_DAYS = 36500  # 100 ปี ใช้แทน "ตลอดชีพ"

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="packages")
    label = models.CharField("ชื่อแพ็กเกจ", max_length=60)
    days = models.PositiveIntegerField("อายุ (วัน)", help_text="ตลอดชีพใส่ 36500")
    price = models.DecimalField("ราคา (บาท)", max_digits=9, decimal_places=2)
    is_active = models.BooleanField("เปิดขาย", default=True)

    class Meta:
        ordering = ["days"]
        constraints = [models.UniqueConstraint(fields=["course", "days"], name="uniq_package_course_days")]

    def __str__(self):
        return f"{self.course_id}:{self.label}"


class Section(SoftDeleteModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="sections")
    title = models.CharField("ชื่อบท", max_length=160)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.course.title} · {self.title}"


class Lesson(SoftDeleteModel):
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField("ชื่อคลิป", max_length=160)
    # เก็บเฉพาะ video id ของ YouTube (Unlisted/Private) — ไม่เก็บ URL เต็ม
    youtube_video_id = models.CharField("YouTube video ID", max_length=20)
    duration_seconds = models.PositiveIntegerField("ความยาว (วินาที)", default=0)
    order = models.PositiveSmallIntegerField(default=0)
    is_free_preview = models.BooleanField("เปิดให้ดูฟรี", default=False)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


def attachment_path(instance, filename):
    return f"lesson_files/{instance.lesson_id}/{filename}"


class LessonAttachment(models.Model):
    """ไฟล์ PDF ประกอบการเรียน — เก็บเป็นไฟล์ส่วนตัว ดาวน์โหลดได้เฉพาะผู้ที่ซื้อคอร์ส"""

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="attachments")
    title = models.CharField(max_length=160)
    file = models.FileField(upload_to=attachment_path, storage=private_storage)

    def __str__(self):
        return self.title

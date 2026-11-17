"""สร้างข้อมูลตั้งต้นสำหรับพัฒนา: หมวดคอร์ส, คอร์สตัวอย่าง, บัญชีแอดมิน/นักเรียนทดสอบ
รหัสผ่านสุ่มและบันทึกลงไฟล์ .seed_credentials (อยู่ใน .gitignore) ไม่แสดงใน log"""
import secrets
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.courses.models import Category, Course, Lesson, Section

SAMPLE_VIDEO = "M7lc1UVf-VE"  # วิดีโอตัวอย่างของ YouTube IFrame API — แทนด้วยคลิป Unlisted จริงผ่านแดชบอร์ด

CATEGORIES = [
    ("TGAT", "tgat", "ภาษาอังกฤษ TGAT", 1),
    ("A-Level", "a-level", "ภาษาอังกฤษ A-Level", 2),
    ("Grammar", "grammar", "ไวยากรณ์ (เร็วๆ นี้)", 3),
    ("Vocab", "vocab", "คำศัพท์ (เร็วๆ นี้)", 4),
    ("Conversation", "conversation", "สนทนา (เร็วๆ นี้)", 5),
    ("Reading", "reading", "การอ่าน (เร็วๆ นี้)", 6),
]


class Command(BaseCommand):
    help = "Seed demo data for local development"

    @transaction.atomic
    def handle(self, *args, **opts):
        cats = {}
        for name, slug, desc, order in CATEGORIES:
            # หมวดที่ยังไม่เปิดสอนซ่อนไว้ก่อน (is_active=False) เปิดได้ในหน้า Django admin
            cats[slug], _ = Category.objects.update_or_create(
                slug=slug, defaults={"name": name, "description": desc, "order": order, "is_active": slug in ("tgat", "a-level")}
            )

        # ตามที่ตกลงกับลูกค้า: ราคา 1,490 บาท เรียนได้ 365 วัน · โปรเปิดตัว 990 บาท 3 เดือนแรก (ปรับวันสิ้นสุดได้ในแดชบอร์ด)
        samples = [
            ("TGAT English — พิชิตข้อสอบ", "tgat-english", "tgat", "ติวครบทุกพาร์ต TGAT ภาษาอังกฤษ ตั้งแต่พื้นฐานถึงเทคนิคทำข้อสอบ", 1490, 365, True),
            ("A-Level English — ตะลุยโจทย์", "a-level-english", "a-level", "เจาะข้อสอบ A-Level ภาษาอังกฤษ พร้อมเฉลยละเอียด", 1490, 365, True),
        ]
        promo_end = timezone.localdate() + timedelta(days=90)
        for title, slug, cat, sub, price, days, pub in samples:
            course, created = Course.objects.get_or_create(
                slug=slug,
                defaults={"cover_url": f"/static/img/covers/{slug.replace('-english', '')}.jpg", "title": title, "category": cats[cat], "subtitle": sub, "price": price, "access_days": days, "promo_price": 990, "promo_ends_on": promo_end,
                          "is_published": pub, "is_featured": True,
                          "description": f"{sub}\n\n• ดูย้อนหลังได้ตลอดอายุคอร์ส\n• มีเอกสาร PDF ประกอบ\n• ระบบจำตำแหน่งที่เรียนค้างไว้"},
            )
            if created:
                for si, st in enumerate(["แนะนำคอร์สและแนวข้อสอบ", "Grammar ที่ออกสอบบ่อย", "Reading Strategies"], start=1):
                    sec = Section.objects.create(course=course, title=st, order=si)
                    for li in range(1, 4):
                        Lesson.objects.create(section=sec, title=f"{st} — คลิปที่ {li}", youtube_video_id=SAMPLE_VIDEO,
                                              duration_seconds=0, order=li, is_free_preview=(si == 1 and li == 1))

        creds = []
        for email, name, staff in [("admin@letmehelp.local", "ผู้ดูแลระบบ", True), ("student@letmehelp.local", "นักเรียนทดสอบ", False)]:
            if User.objects.filter(email=email).exists():
                continue
            pwd = secrets.token_urlsafe(12)
            User.objects.create_user(email=email, password=pwd, full_name=name, phone="0800000000",
                                     is_staff=staff, is_superuser=staff)
            creds.append(f"{email}\t{pwd}")
        if creds:
            path = Path(settings.BASE_DIR) / ".seed_credentials"
            with path.open("a") as fh:
                fh.write("\n".join(creds) + "\n")
            path.chmod(0o600)
            self.stdout.write(self.style.SUCCESS(f"สร้างบัญชีทดสอบ {len(creds)} บัญชี — รหัสผ่านอยู่ใน {path.name}"))
        self.stdout.write(self.style.SUCCESS("seed เสร็จแล้ว"))

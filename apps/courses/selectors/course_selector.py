from django.db.models import Count, OuterRef, Prefetch, Q, Subquery

from apps.courses.models import Category, Course, Lesson, Section

_CARD_FIELDS = (
    "id", "title", "slug", "subtitle", "thumbnail", "price", "access_days",
    "category__name", "category__slug", "updated_at",
)


# วิดีโอแรกของคอร์ส — ใช้ดึงภาพปกอัตโนมัติจาก YouTube เมื่อไม่ได้ตั้งรูปปก
_FIRST_VIDEO = Subquery(
    Lesson.objects.filter(section__course=OuterRef("pk"), section__deleted_at__isnull=True).order_by("section__order", "order").values("youtube_video_id")[:1]
)


# นับเฉพาะคลิปและบทที่ยังไม่อยู่ในถังขยะ (join ไม่ผ่าน manager จึงต้องกรองเอง)
_ALIVE_LESSON = Q(sections__deleted_at__isnull=True, sections__lessons__deleted_at__isnull=True)


def list_categories():
    return list(Category.objects.filter(is_active=True).only("id", "name", "slug", "description"))


def _published_cards():
    return (
        Course.objects.filter(is_published=True)
        .select_related("category")
        .only("id", "title", "slug", "subtitle", "thumbnail", "cover_url", "price", "promo_price", "promo_ends_on", "access_days", "category__name", "category__slug")
        .annotate(lesson_count=Count("sections__lessons", filter=_ALIVE_LESSON, distinct=True), first_video_id=_FIRST_VIDEO)
        .order_by("-created_at", "id")
    )


def featured_courses(limit=6):
    return list(_published_cards().filter(is_featured=True)[:limit]) or list(_published_cards()[:limit])


def search_published_courses(category_slug=None):
    qs = _published_cards()
    if category_slug:
        qs = qs.filter(category__slug=category_slug)
    return qs


def get_published_course_detail(slug):
    """ดึงคอร์ส + บท + คลิป ใน query ชุดเดียว (กัน N+1)"""
    lessons = Lesson.objects.only(
        "id", "section_id", "title", "duration_seconds", "order", "is_free_preview"
    )
    sections = Section.objects.prefetch_related(Prefetch("lessons", queryset=lessons))
    return (
        Course.objects.filter(slug=slug, is_published=True)
        .select_related("category")
        .prefetch_related(Prefetch("sections", queryset=sections), "packages")
        .annotate(first_video_id=_FIRST_VIDEO)
        .first()
    )


def published_courses_for_sitemap():
    return list(Course.objects.filter(is_published=True).only("id", "slug", "updated_at"))


def get_course_with_content(course_id):
    """ใช้ในหน้าเรียนและหน้าจัดการเนื้อหา — รวมไฟล์แนบ (เห็นคอร์สที่เลิกเผยแพร่/อยู่ในถังขยะด้วย เพื่อให้ผู้ที่ซื้อแล้วยังเรียนได้)"""
    lessons = Lesson.objects.prefetch_related("attachments")
    sections = Section.objects.prefetch_related(Prefetch("lessons", queryset=lessons))
    return (
        Course.all_objects.select_related("category")
        .prefetch_related(Prefetch("sections", queryset=sections), "packages")
        .annotate(first_video_id=_FIRST_VIDEO)
        .filter(pk=course_id)
        .first()
    )


def dashboard_course_list():
    """รายการคอร์สสำหรับหลังบ้าน (ไม่รวมถังขยะ) พร้อมจำนวนคลิป/นักเรียนที่ยังเรียนอยู่"""
    from django.utils import timezone

    return (
        Course.objects.select_related("category")
        .only("id", "title", "slug", "price", "promo_price", "promo_ends_on", "access_days", "is_published", "is_featured", "created_at", "category__name", "category__slug")
        .annotate(
            student_count=Count("enrollments", filter=Q(enrollments__status="active", enrollments__expires_at__gt=timezone.now()), distinct=True),
            lesson_count=Count("sections__lessons", filter=_ALIVE_LESSON, distinct=True),
        )
    )


def free_preview_lessons():
    """คลิปที่เปิดให้ดูฟรีของคอร์สที่เผยแพร่แล้ว จัดกลุ่มตามคอร์ส (ใช้หน้า 'ทดลองเรียนฟรี')"""
    rows = (
        Lesson.objects.filter(is_free_preview=True, section__course__is_published=True, section__course__deleted_at__isnull=True, section__deleted_at__isnull=True)
        .select_related("section__course__category")
        .only(
            "id", "title", "youtube_video_id", "duration_seconds",
            "section__title", "section__course__id", "section__course__title", "section__course__slug",
            "section__course__category__name", "section__course__category__slug",
        )
        .order_by("section__course__created_at", "section__order", "order")
    )
    groups = {}
    for lesson in rows:
        course = lesson.section.course
        groups.setdefault(course.pk, {"course": course, "lessons": []})["lessons"].append(lesson)
    return list(groups.values())

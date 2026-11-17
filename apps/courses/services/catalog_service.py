"""จัดการข้อมูลคอร์สจากหลังบ้าน: หมวด คอร์ส บท คลิป ไฟล์แนบ แพ็กเกจ — ทุกการเขียนมีบันทึกประวัติ (AuditLog)
ลบ = ถังขยะ (soft delete) กู้คืนได้ · ข้อผิดพลาดทางธุรกิจ throw ActionError ให้ view แสดงข้อความ"""
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.core.services import audit_service
from apps.courses.models import Category, Course, CoursePackage, Lesson, LessonAttachment, Section
from apps.core.exceptions import ActionError


def _save_form(form, request, label_model: str):
    created = form.instance.pk is None
    obj = form.save()
    audit_service.log(
        request=request, action="create" if created else "update", obj=obj,
        changes={} if created else audit_service.form_changes(form),
    )
    return obj


# ---- หมวด -----------------------------------------------------------------
def save_category(form, request):
    return _save_form(form, request, "Category")


def toggle_category(category: Category, request):
    category.is_active = not category.is_active
    category.save(update_fields=["is_active"])
    audit_service.log(request=request, action="update", obj=category, changes={"is_active": [not category.is_active, category.is_active]})
    return "เปิดหมวดแล้ว" if category.is_active else "ปิดหมวดแล้ว"


def delete_category(category: Category, request):
    n = Course.objects.filter(category=category).count()
    if n:
        raise ActionError(f"ยังมี {n} คอร์สในหมวดนี้ ย้ายหรือลบคอร์สก่อน")
    category.soft_delete()
    audit_service.log(request=request, action="delete", obj=category)
    return "ย้ายหมวดไปถังขยะแล้ว"


# ---- คอร์ส ------------------------------------------------------------------
def save_course(form, request):
    return _save_form(form, request, "Course")


def toggle_course(course: Course, field: str, request):
    if field not in ("is_published", "is_featured"):
        raise ActionError("ฟิลด์ไม่ถูกต้อง")
    setattr(course, field, not getattr(course, field))
    course.save(update_fields=[field])
    audit_service.log(request=request, action="update", obj=course, changes={field: [not getattr(course, field), getattr(course, field)]})
    if field == "is_published":
        return "เผยแพร่คอร์สแล้ว" if course.is_published else "เลิกเผยแพร่แล้ว (นักเรียนที่ซื้อแล้วยังเรียนได้)"
    return "ตั้งเป็นคอร์สแนะนำแล้ว" if course.is_featured else "เอาออกจากคอร์สแนะนำแล้ว"


def delete_course(course: Course, request):
    students = course.enrollments.filter(status="active", expires_at__gt=timezone.now()).count()
    course.is_published = False
    course.deleted_at = timezone.now()
    course.save(update_fields=["is_published", "deleted_at"])
    audit_service.log(request=request, action="delete", obj=course, changes={"active_students": students})
    tail = f" (นักเรียน {students} คนที่ซื้อแล้วยังเรียนต่อได้)" if students else ""
    return "ย้ายคอร์สไปถังขยะแล้ว" + tail


@transaction.atomic
def duplicate_course(course: Course, request) -> Course:
    """คัดลอกคอร์ส + บท + คลิป + แพ็กเกจ (ไม่คัดลอกไฟล์ PDF/นักเรียน) ตั้งเป็นฉบับร่าง"""
    base = f"{course.slug}-copy"
    slug, n = base, 1
    while Course.all_objects.filter(slug=slug).exists():
        n += 1
        slug = f"{base}-{n}"
    new = Course.objects.create(
        category=course.category, title=f"{course.title} (สำเนา)", slug=slug, subtitle=course.subtitle,
        description=course.description, cover_url=course.cover_url, price=course.price, promo_price=course.promo_price, promo_ends_on=course.promo_ends_on, book_url=course.book_url,
        access_days=course.access_days, is_published=False, is_featured=False,
    )
    for sec in course.sections.all():
        ns = Section.objects.create(course=new, title=sec.title, order=sec.order)
        Lesson.objects.bulk_create(
            Lesson(section=ns, title=l.title, youtube_video_id=l.youtube_video_id, duration_seconds=l.duration_seconds,
                   order=l.order, is_free_preview=l.is_free_preview)
            for l in sec.lessons.all()
        )
    CoursePackage.objects.bulk_create(
        CoursePackage(course=new, label=p.label, days=p.days, price=p.price, is_active=p.is_active) for p in course.packages.all()
    )
    audit_service.log(request=request, action="create", obj=new, changes={"duplicated_from": course.pk})
    return new


def bulk_course_action(ids, action: str, request) -> str:
    qs = Course.objects.filter(pk__in=ids)
    n = qs.count()
    if action == "publish":
        qs.update(is_published=True)
    elif action == "unpublish":
        qs.update(is_published=False)
    elif action == "delete":
        qs.update(is_published=False, deleted_at=timezone.now())
    else:
        raise ActionError("คำสั่งไม่ถูกต้อง")
    audit_service.log(request=request, action=f"bulk_{action}", model="Course", object_id="", label=f"{n} คอร์ส", changes={"ids": list(ids)})
    return f"ทำรายการกับ {n} คอร์สแล้ว"


# ---- บท / คลิป -----------------------------------------------------------------
def _renumber(items):
    for i, obj in enumerate(items, start=1):
        if obj.order != i:
            obj.order = i
            obj.save(update_fields=["order"])


def _move(obj, siblings, direction: str):
    items = list(siblings.order_by("order", "id"))
    idx = next(i for i, o in enumerate(items) if o.pk == obj.pk)
    j = idx - 1 if direction == "up" else idx + 1
    if 0 <= j < len(items):
        items[idx], items[j] = items[j], items[idx]
    _renumber(items)
    return "เลื่อนลำดับแล้ว"


def save_section(form, request, course: Course):
    form.instance.course = course
    return _save_form(form, request, "Section")


def move_section(section: Section, direction: str):
    return _move(section, Section.objects.filter(course_id=section.course_id), direction)


@transaction.atomic
def delete_section(section: Section, request):
    now = timezone.now()
    section.deleted_at = now
    section.save(update_fields=["deleted_at"])
    Lesson.objects.filter(section=section).update(deleted_at=now)  # ลบคลิปในบทไปด้วย (เวลาเดียวกัน เพื่อกู้คืนคู่กัน)
    audit_service.log(request=request, action="delete", obj=section)
    return "ย้ายบทไปถังขยะแล้ว"


def save_lesson(form, request, section: Section):
    form.instance.section = section
    return _save_form(form, request, "Lesson")


def move_lesson(lesson: Lesson, direction: str):
    return _move(lesson, Lesson.objects.filter(section_id=lesson.section_id), direction)


def delete_lesson(lesson: Lesson, request):
    lesson.soft_delete()
    audit_service.log(request=request, action="delete", obj=lesson)
    return "ย้ายคลิปไปถังขยะแล้ว"


def duplicate_lesson(lesson: Lesson, request) -> Lesson:
    last = Lesson.objects.filter(section_id=lesson.section_id).order_by("-order").values_list("order", flat=True).first() or 0
    new = Lesson.objects.create(
        section=lesson.section, title=f"{lesson.title} (สำเนา)", youtube_video_id=lesson.youtube_video_id,
        duration_seconds=lesson.duration_seconds, order=last + 1, is_free_preview=lesson.is_free_preview,
    )
    audit_service.log(request=request, action="create", obj=new, changes={"duplicated_from": lesson.pk})
    return new


# ---- ไฟล์แนบ / แพ็กเกจ ---------------------------------------------------------------
def save_attachment(form, request, lesson: Lesson):
    form.instance.lesson = lesson
    return _save_form(form, request, "LessonAttachment")


def delete_attachment(att: LessonAttachment, request):
    audit_service.log(request=request, action="delete", obj=att)
    att.file.delete(save=False)
    att.delete()
    return "ลบไฟล์แนบแล้ว"


def save_package(form, request, course: Course):
    form.instance.course = course
    return _save_form(form, request, "CoursePackage")


def delete_package(pkg: CoursePackage, request):
    audit_service.log(request=request, action="delete", obj=pkg)
    pkg.delete()
    return "ลบแพ็กเกจแล้ว"


def toggle_package(pkg: CoursePackage, request):
    pkg.is_active = not pkg.is_active
    pkg.save(update_fields=["is_active"])
    audit_service.log(request=request, action="update", obj=pkg, changes={"is_active": [not pkg.is_active, pkg.is_active]})
    return "เปิดขายแพ็กเกจแล้ว" if pkg.is_active else "ปิดขายแพ็กเกจแล้ว"

"""หลังบ้าน: หมวดคอร์ส / คอร์ส / บท-คลิป-ไฟล์แนบ / แพ็กเกจ — view บางๆ: รับ request → เรียก service → ตอบ"""
import json

from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from apps.core.decorators import staff_required
from apps.core.exceptions import ActionError
from apps.courses.forms import AttachmentForm, CategoryForm, CourseForm, LessonForm, PackageForm, SectionForm
from apps.courses.models import Category, Course, CoursePackage, Lesson, LessonAttachment, Section
from apps.courses.selectors import course_selector
from apps.courses.services import catalog_service as svc
from apps.dashboard.crud import json_action, modal_form
from apps.dashboard.selectors.list_params import paginate
from django.db.models import Count, Q


# ---------- หมวดคอร์ส ----------
@staff_required
def category_list(request):
    qs = Category.objects.annotate(course_count=Count("courses", filter=Q(courses__deleted_at__isnull=True)))
    ls = paginate(request, qs, search=("name", "slug"), sorts={"order": ("order", "name"), "name": ("name",), "courses": ("course_count",)}, default_sort="order", per_page=50)
    return render(request, "dashboard/category_list.html", {"ls": ls})


@staff_required
def category_form(request, category_id=None):
    cat = get_object_or_404(Category, pk=category_id) if category_id else None
    form = CategoryForm(request.POST or None, instance=cat)
    return modal_form(request, form, save=lambda f: svc.save_category(f, request),
                      title="แก้ไขหมวดคอร์ส" if cat else "เพิ่มหมวดคอร์ส", ok_message="บันทึกหมวดแล้ว", back=reverse("dashboard:category_list"))


@json_action
def category_toggle(request, category_id):
    return svc.toggle_category(get_object_or_404(Category, pk=category_id), request)


@json_action
def category_delete(request, category_id):
    return svc.delete_category(get_object_or_404(Category, pk=category_id), request)


# ---------- คอร์ส ----------
@staff_required
def course_list(request):
    def status(qs, v):
        return qs.filter(is_published=(v == "published"))

    ls = paginate(
        request, course_selector.dashboard_course_list(),
        search=("title", "slug", "subtitle"),
        filters={"category": "category_id", "status": status},
        sorts={"created": ("created_at",), "title": ("title",), "price": ("price",), "students": ("student_count",)},
        default_sort="-created",
    )
    return render(request, "dashboard/course_list.html", {
        "ls": ls,
        "filters_ui": [
            ("category", "หมวด", list(Category.objects.values_list("id", "name"))),
            ("status", "สถานะ", [("published", "เผยแพร่"), ("draft", "ฉบับร่าง")]),
        ],
    })


@staff_required
def course_form(request, course_id=None):
    course = get_object_or_404(Course, pk=course_id) if course_id else None
    form = CourseForm(request.POST or None, request.FILES or None, instance=course)

    def save(f):
        obj = svc.save_course(f, request)
        if course is None:  # สร้างใหม่ → ไปหน้าเนื้อหาต่อเลย
            f.redirect_to = reverse("dashboard:course_content", args=[obj.pk])

    resp = modal_form(request, form, save=save, title="แก้ไขคอร์ส" if course else "สร้างคอร์สใหม่", ok_message="บันทึกคอร์สแล้ว",
                      back=reverse("dashboard:course_list"))
    if getattr(form, "redirect_to", None) and resp.status_code == 302:
        resp["Location"] = form.redirect_to
    return resp


@json_action
def course_toggle(request, course_id, field):
    return svc.toggle_course(get_object_or_404(Course, pk=course_id), field, request)


@json_action
def course_duplicate(request, course_id):
    new = svc.duplicate_course(get_object_or_404(Course, pk=course_id), request)
    return f"สร้างสำเนาแล้ว: {new.title}"


@json_action
def course_delete(request, course_id):
    return svc.delete_course(get_object_or_404(Course, pk=course_id), request)


@json_action
def course_bulk(request):
    body = json.loads(request.body or "{}")
    ids = [int(i) for i in body.get("ids", []) if str(i).isdigit()]
    if not ids:
        raise ActionError("ยังไม่ได้เลือกรายการ")
    return svc.bulk_course_action(ids, body.get("action", ""), request)


# ---------- เนื้อหาคอร์ส ----------
@staff_required
def course_content(request, course_id):
    course = course_selector.get_course_with_content(course_id)
    if course is None or course.deleted_at:
        raise Http404
    from apps.courses.services.pricing_service import duration_label

    return render(request, "dashboard/course_content.html", {
        "course": course,
        "base_label": duration_label(course.access_days),
    })


def _section(section_id):
    return get_object_or_404(Section, pk=section_id)


def _lesson(lesson_id):
    return get_object_or_404(Lesson.objects.select_related("section"), pk=lesson_id)


@staff_required
def section_form(request, course_id=None, section_id=None):
    section = _section(section_id) if section_id else None
    course = section.course if section else get_object_or_404(Course, pk=course_id)
    form = SectionForm(request.POST or None, instance=section)
    return modal_form(request, form, save=lambda f: svc.save_section(f, request, course),
                      title="แก้ไขบท" if section else "เพิ่มบท", ok_message="บันทึกบทแล้ว",
                      back=reverse("dashboard:course_content", args=[course.pk]))


@json_action
def section_move(request, section_id, direction):
    return svc.move_section(_section(section_id), direction)


@json_action
def section_delete(request, section_id):
    return svc.delete_section(_section(section_id), request)


@staff_required
def lesson_form(request, section_id=None, lesson_id=None):
    lesson = _lesson(lesson_id) if lesson_id else None
    section = lesson.section if lesson else _section(section_id)
    form = LessonForm(request.POST or None, instance=lesson)
    return modal_form(request, form, save=lambda f: svc.save_lesson(f, request, section),
                      title="แก้ไขคลิป" if lesson else "เพิ่มคลิป", ok_message="บันทึกคลิปแล้ว",
                      intro=f"บท: {section.title} · อัปโหลดวิดีโอเป็น Unlisted/Private บน YouTube แล้ววางลิงก์",
                      back=reverse("dashboard:course_content", args=[section.course_id]))


@json_action
def lesson_move(request, lesson_id, direction):
    return svc.move_lesson(_lesson(lesson_id), direction)


@json_action
def lesson_delete(request, lesson_id):
    return svc.delete_lesson(_lesson(lesson_id), request)


@json_action
def lesson_duplicate(request, lesson_id):
    svc.duplicate_lesson(_lesson(lesson_id), request)
    return "ทำสำเนาคลิปแล้ว"


@staff_required
def attachment_form(request, lesson_id):
    lesson = _lesson(lesson_id)
    form = AttachmentForm(request.POST or None, request.FILES or None)
    return modal_form(request, form, save=lambda f: svc.save_attachment(f, request, lesson),
                      title="แนบไฟล์ PDF", ok_message="แนบไฟล์แล้ว", intro=f"คลิป: {lesson.title}",
                      back=reverse("dashboard:course_content", args=[lesson.section.course_id]))


@json_action
def attachment_delete(request, attachment_id):
    return svc.delete_attachment(get_object_or_404(LessonAttachment, pk=attachment_id), request)


# ---------- แพ็กเกจ ----------
@staff_required
def package_form(request, course_id=None, package_id=None):
    pkg = get_object_or_404(CoursePackage, pk=package_id) if package_id else None
    course = pkg.course if pkg else get_object_or_404(Course, pk=course_id)
    form = PackageForm(request.POST or None, instance=pkg, course=course)
    return modal_form(request, form, save=lambda f: svc.save_package(f, request, course),
                      title="แก้ไขแพ็กเกจ" if pkg else "เพิ่มแพ็กเกจ", ok_message="บันทึกแพ็กเกจแล้ว",
                      intro="ตลอดชีพใส่ 36500 วัน · แพ็กเกจหลักคือราคา/อายุในข้อมูลคอร์ส",
                      back=reverse("dashboard:course_content", args=[course.pk]))


@json_action
def package_toggle(request, package_id):
    return svc.toggle_package(get_object_or_404(CoursePackage, pk=package_id), request)


@json_action
def package_delete(request, package_id):
    return svc.delete_package(get_object_or_404(CoursePackage, pk=package_id), request)

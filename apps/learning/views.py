import json
from datetime import date

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.courses.models import LessonAttachment
from apps.courses.selectors.course_selector import get_course_with_content
from apps.enrollments.selectors.enrollment_selector import get_active_enrollment, user_enrollments
from apps.payments.models import Order

from apps.accounts.forms import ProfileForm

from .selectors import learning_selector as sel
from .services import note_service, progress_service


@login_required
def my_courses(request):
    enrollments = user_enrollments(request.user)
    percents = sel.course_progress_percent(request.user, [e.course_id for e in enrollments])
    for e in enrollments:
        e.percent = percents.get(e.course_id, 0)
        e.is_active = e.status == "active" and e.expires_at > timezone.now()
        e.days_left = (e.expires_at - timezone.now()).days if e.is_active else 0
    waiting = list(
        Order.objects.filter(user=request.user, status__in=[Order.Status.REVIEWING, Order.Status.REJECTED])
        .select_related("course")
        .only("id", "status", "amount", "course__title", "course__slug")
    )
    active_ids = [e.course_id for e in enrollments if e.is_active]
    return render(
        request,
        "learning/my_courses.html",
        {
            "enrollments": enrollments,
            "waiting_orders": waiting,
            "continue_item": sel.last_studied(request.user, active_ids),
            "stats": sel.study_stats(request.user),
            "week": sel.week_strip(request.user),
            "active_count": len(active_ids),
            "profile_form": ProfileForm(instance=request.user),
        },
    )


def player(request, slug, lesson_id=None):
    """หน้าเรียน — คลิปที่เปิดให้ดูฟรีดูได้โดยไม่ต้องล็อกอิน (ไม่บันทึกความคืบหน้า)"""
    from apps.courses.models import Course

    course_id = Course.all_objects.filter(slug=slug).values_list("id", flat=True).first()
    if course_id is None:
        raise Http404
    course = get_course_with_content(course_id)
    authed = request.user.is_authenticated
    enrollment = get_active_enrollment(request.user, course.pk) if authed else None
    progress = sel.progress_map(request.user, course.pk) if authed else {}
    if (course.deleted_at or not course.is_published) and enrollment is None:
        raise Http404  # เลิกเผยแพร่/ถูกลบ: ไม่ขายต่อ แต่ผู้ที่ซื้อแล้วยังเข้าเรียนได้

    if lesson_id is None:
        lesson_id = sel.first_unfinished_lesson_id(course, progress)
    lesson = next(
        (l for s in course.sections.all() for l in s.lessons.all() if l.pk == lesson_id), None
    )
    if lesson is None:
        raise Http404

    if enrollment is None and not lesson.is_free_preview:
        if not authed:
            return redirect_to_login(request.get_full_path())
        return redirect("payments:checkout", slug=course.slug)  # ยังไม่ได้ซื้อ/หมดอายุ → ไปชำระ/ต่ออายุ

    last_pos = progress.get(lesson.pk, (0, False))[0]
    all_lessons = [l for s in course.sections.all() for l in s.lessons.all()]
    idx = all_lessons.index(lesson)
    done = sum(1 for l in all_lessons if progress.get(l.pk, (0, False))[1])
    return render(
        request,
        "learning/player.html",
        {
            "course": course,
            "lesson": lesson,
            "progress": progress,
            "course_percent": round(done * 100 / len(all_lessons)) if all_lessons else 0,
            "lessons_done": done,
            "lessons_total": len(all_lessons),
            "prev_lesson": all_lessons[idx - 1] if idx > 0 else None,
            "start_at": progress_service.resume_position(last_pos),
            "can_track": enrollment is not None,
            "next_lesson": all_lessons[idx + 1] if idx + 1 < len(all_lessons) else None,
            "enrollment": enrollment,
        },
    )


@login_required
@require_POST
def save_progress(request):
    """Ajax: client ส่งตำแหน่งวิดีโอ + เวลาที่ดูจริงมาเป็นระยะ"""
    try:
        body = json.loads(request.body)
        lesson_id = int(body["lesson_id"])
        position = int(float(body.get("position", 0)))
        delta = int(float(body.get("delta", 0)))
        duration = int(float(body.get("duration", 0)))
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"ok": False}, status=400)
    lesson = sel.get_lesson_with_course(lesson_id)
    if lesson is None:
        raise Http404
    if get_active_enrollment(request.user, lesson.section.course_id) is None:
        return JsonResponse({"ok": False, "error": "no_access"}, status=403)
    progress = progress_service.save_progress(
        user=request.user, lesson=lesson, position=position, watched_delta=delta, client_duration=duration
    )
    return JsonResponse({"ok": True, "completed": progress.completed})


@login_required
def study_dashboard(request):
    return render(request, "learning/study.html", {"stats": sel.study_stats(request.user)})


@login_required
@require_GET
def calendar_data(request):
    today = timezone.localdate()
    try:
        year, month = (int(x) for x in request.GET.get("month", f"{today.year}-{today.month}").split("-"))
        date(year, month, 1)
    except ValueError:
        return JsonResponse({"error": "bad month"}, status=400)
    return JsonResponse({"year": year, "month": month, "days": sel.month_calendar(request.user, year, month)})


@login_required
def download_attachment(request, attachment_id):
    att = (
        LessonAttachment.objects.select_related("lesson__section")
        .only("id", "title", "file", "lesson__id", "lesson__is_free_preview", "lesson__section__course_id")
        .filter(pk=attachment_id)
        .first()
    )
    if att is None:
        raise Http404
    if not att.lesson.is_free_preview and get_active_enrollment(request.user, att.lesson.section.course_id) is None:
        raise Http404
    return FileResponse(att.file.open("rb"), as_attachment=True, filename=f"{att.title}.pdf")


@login_required
def lesson_note(request, lesson_id):
    """Ajax: อ่าน/บันทึกสมุดโน้ตส่วนตัวของคลิป (บันทึกอัตโนมัติจากหน้าเรียน)"""
    lesson = sel.get_lesson_with_course(lesson_id)
    if lesson is None:
        raise Http404
    if get_active_enrollment(request.user, lesson.section.course_id) is None:
        return JsonResponse({"ok": False, "error": "no_access"}, status=403)
    if request.method == "POST":
        try:
            content = json.loads(request.body).get("content", "")
        except (ValueError, AttributeError):
            return JsonResponse({"ok": False}, status=400)
        note = note_service.save_note(user=request.user, lesson=lesson, content=content)
        return JsonResponse({"ok": True, "updated_at": timezone.localtime(note.updated_at).strftime("%H:%M:%S")})
    if request.method != "GET":
        return JsonResponse({"ok": False}, status=405)
    return JsonResponse({"ok": True, "content": note_service.get_note_content(user=request.user, lesson_id=lesson.pk)})

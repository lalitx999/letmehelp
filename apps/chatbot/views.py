import json

from asgiref.sync import sync_to_async
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from apps.enrollments.selectors.enrollment_selector import get_active_enrollment
from apps.learning.selectors.learning_selector import get_lesson_with_course

from .services import chat_service


def _lesson_context(user, lesson_id):
    """โหมดติวเตอร์ใช้ได้เฉพาะคนที่มีสิทธิ์เรียนคลิปนั้น (หรือคลิปที่เปิดฟรี) — ไม่ให้ใช้เป็นช่องทางดึงข้อมูลคอร์สที่ยังไม่ได้ซื้อ"""
    try:
        lesson = get_lesson_with_course(int(lesson_id))
    except (TypeError, ValueError):
        return None
    if lesson is None:
        return None
    course = lesson.section.course
    allowed = lesson.is_free_preview or (
        user.is_authenticated and get_active_enrollment(user, course.pk) is not None
    )
    if not allowed:
        return None
    category = course.category.name if hasattr(course, "category") and course.category_id else ""
    return {"title": lesson.title, "course": course.title, "category": category}


@require_POST
async def chat(request):
    """async view: การรอ Claude (หลายวินาที) ไม่บล็อก worker เมื่อรันบน ASGI — ดู chat_service"""
    try:
        body = json.loads(request.body)
    except ValueError:
        return JsonResponse({"error": "bad_request"}, status=400)

    history = chat_service.clean_history(body.get("messages"))
    if not history or history[-1]["role"] != "user":
        return JsonResponse({"error": "no_message"}, status=400)

    user = await request.auser()
    ident = f"u{user.pk}" if user.is_authenticated else f"ip{request.META.get('REMOTE_ADDR', '')}"
    if await chat_service.is_rate_limited(ident):
        return JsonResponse(
            {"reply": "ส่งข้อความถี่เกินไป รอสักครู่แล้วลองใหม่อีกครั้งนะ", "source": "limit", "suggestions": []}, status=429
        )

    lesson = await sync_to_async(_lesson_context)(user, body.get("lesson_id")) if body.get("lesson_id") else None
    result = await chat_service.reply(history=history, lesson=lesson)
    return JsonResponse({"reply": result.text, "source": result.source, "suggestions": result.suggestions, "mode": "tutor" if lesson else "public"})

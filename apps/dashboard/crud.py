"""ตัวช่วย CRUD ของหลังบ้าน: ฟอร์มที่เปิดได้ทั้งแบบ modal (Ajax) และหน้าเต็ม + ปุ่มลัดแบบ POST ที่ตอบ JSON"""
from functools import wraps

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import staff_required
from apps.core.exceptions import ActionError  # noqa: F401  (re-export ให้ view ใช้)


def is_fetch(request) -> bool:
    return request.headers.get("X-Requested-With") == "fetch"


def modal_form(request, form, *, save, title, submit="บันทึก", ok_message="บันทึกแล้ว", intro="", back=None, submit_class="btn-dark"):
    """GET: แสดงฟอร์ม (partial สำหรับ modal หรือหน้าเต็ม) · POST ถูกต้อง: save(form) แล้วตอบ JSON/redirect · ผิดพลาด: แสดงฟอร์มพร้อม error (422)"""
    status = 200
    if request.method == "POST":
        if form.is_valid():
            try:
                save(form)
            except ActionError as exc:
                form.add_error(None, str(exc))
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                if is_fetch(request):
                    return JsonResponse({"ok": True, "message": ok_message})
                messages.success(request, ok_message)
                return redirect(back or request.META.get("HTTP_REFERER") or "dashboard:overview")
        status = 422
    ctx = {"form": form, "title": title, "submit": submit, "intro": intro, "action": request.get_full_path(),
           "back": back, "submit_class": submit_class}
    template = "dashboard/_modal_form.html" if is_fetch(request) else "dashboard/form_page.html"
    return render(request, template, ctx, status=status)


def json_action(view):
    """POST เท่านั้น + ต้องเป็นแอดมิน + แปลง ActionError เป็น JSON — ใช้กับปุ่มลบ/กู้คืน/สลับสถานะ/เลื่อนลำดับ"""

    @wraps(view)
    @staff_required
    @require_POST
    def wrapper(request, *args, **kwargs):
        try:
            result = view(request, *args, **kwargs)
        except ActionError as exc:
            return JsonResponse({"ok": False, "error": str(exc)}, status=400)
        if isinstance(result, JsonResponse):
            return result
        return JsonResponse({"ok": True, "message": result or "ทำรายการแล้ว"})

    return wrapper

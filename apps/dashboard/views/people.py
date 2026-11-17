"""หลังบ้าน: นักเรียน + สิทธิ์เรียน"""
import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone

from apps.accounts.forms import AdminUserForm, PasswordResetForm
from apps.accounts.models import User
from apps.accounts.services import account_service
from apps.core.decorators import staff_required
from apps.core.exceptions import ActionError
from apps.dashboard.crud import json_action, modal_form
from apps.dashboard.selectors import people_selector as sel
from apps.dashboard.selectors.list_params import paginate
from apps.enrollments.forms import ExtendForm, GrantForm
from apps.enrollments.models import Enrollment
from apps.enrollments.services import enrollment_service
from apps.learning.selectors.learning_selector import study_stats
from apps.notifications.services import reminder_service


# ---------- นักเรียน ----------
@staff_required
def student_list(request):
    ls = paginate(
        request, sel.students_qs(), search=("full_name", "email", "phone"),
        filters={"state": sel.student_enrollment_filter, "active": lambda qs, v: qs.filter(is_active=(v == "1"))},
        sorts={"joined": ("date_joined",), "name": ("full_name",), "courses": ("course_count",), "login": ("last_login",)},
        default_sort="-joined", per_page=25,
    )
    return render(request, "dashboard/student_list.html", {
        "ls": ls,
        "filters_ui": [
            ("state", "การเรียน", [("active", "กำลังเรียน"), ("expired", "หมดอายุแล้ว"), ("none", "ยังไม่เคยซื้อ")]),
            ("active", "บัญชี", [("1", "ใช้งานอยู่"), ("0", "ปิดอยู่")]),
        ],
    })


@staff_required
def student_detail(request, user_id):
    student = get_object_or_404(User, pk=user_id, is_staff=False)
    return render(request, "dashboard/student_detail.html", {
        "s": student, "enrollments": sel.student_enrollments(student), "orders": sel.student_orders(student),
        "stats": study_stats(student), "now": timezone.now(),
    })


@staff_required
def student_form(request, user_id=None):
    student = get_object_or_404(User, pk=user_id, is_staff=False) if user_id else None
    form = AdminUserForm(request.POST or None, instance=student, creating=student is None)
    result = {}

    def save(f):
        if student:
            account_service.update_by_admin(f, request)
        else:
            user, pwd = account_service.create_by_admin(f, request)
            result.update(user=user, pwd=pwd)

    resp = modal_form(request, form, save=save, title="แก้ไขนักเรียน" if student else "เพิ่มนักเรียน",
                      ok_message="บันทึกแล้ว", back=reverse("dashboard:student_list"))
    if result and resp.status_code == 302:
        messages.info(request, f"สร้างบัญชีแล้ว — อีเมล {result['user'].email} · รหัสผ่านชั่วคราว: {result['pwd']} (แจ้งนักเรียนและให้เปลี่ยนรหัสผ่านเอง)")
        resp["Location"] = reverse("dashboard:student_detail", args=[result["user"].pk])
    return resp


@json_action
def student_toggle(request, user_id):
    return account_service.set_active(get_object_or_404(User, pk=user_id, is_staff=False), request)


@staff_required
def student_password(request, user_id):
    student = get_object_or_404(User, pk=user_id)  # ใช้ได้ทั้งนักเรียนและแอดมิน
    form = PasswordResetForm(request.POST or None)
    out = {}

    def save(f):
        out["pwd"] = account_service.reset_password(student, request, f.cleaned_data.get("password", ""))

    resp = modal_form(request, form, save=save, title="รีเซ็ตรหัสผ่าน", submit="ตั้งรหัสผ่านใหม่", intro=f"นักเรียน: {student.full_name}",
                      ok_message="ตั้งรหัสผ่านแล้ว", back=reverse("dashboard:admin_list" if student.is_staff else "dashboard:student_detail", args=[student.pk] if not student.is_staff else []))
    if out and resp.status_code == 200 and request.headers.get("X-Requested-With") == "fetch":
        return JsonResponse({"ok": True, "message": f"รหัสผ่านใหม่: {out['pwd']} (แจ้งนักเรียน — แสดงครั้งเดียว)"})
    if out and resp.status_code == 302:
        messages.info(request, f"รหัสผ่านใหม่: {out['pwd']} (แจ้งนักเรียน)")
    return resp


# ---------- สิทธิ์เรียน ----------
@staff_required
def enrollment_list(request):
    tab = request.GET.get("tab") or "soon"  # ค่าเริ่มต้น: สิทธิ์ที่ใกล้หมดอายุ
    qs = sel.enrollment_tab_filter(sel.enrollments_qs(), tab)
    ls = paginate(
        request, qs, search=("user__full_name", "user__email", "user__phone", "course__title"),
        filters={"source": "source"}, sorts={"expires": ("expires_at",), "started": ("started_at",), "student": ("user__full_name",)},
        default_sort="expires", per_page=25,
    )
    return render(request, "dashboard/enrollment_list.html", {
        "ls": ls, "tab": tab, "now": timezone.now(),
        "tabs": [("soon", "ใกล้หมด 30 วัน", "clock"), ("expired", "หมดอายุแล้ว", "exclamation-circle"), ("active", "กำลังเรียน", "check-circle"),
                 ("cancelled", "ยกเลิกแล้ว", "x-circle"), ("all", "ทั้งหมด", "collection")],
    })


@staff_required
def enrollment_grant(request):
    form = GrantForm(request.POST or None, initial={"email": request.GET.get("email", "")})

    def save(f):
        d = f.cleaned_data
        enrollment_service.grant_manual(user=f.user, course=d["course"], days=d["days"], source=d["source"], note=d["note"], request=request)

    return modal_form(request, form, save=save, title="มอบสิทธิ์เรียน", submit="มอบสิทธิ์", ok_message="มอบสิทธิ์เรียนแล้ว",
                      intro="ถ้านักเรียนมีสิทธิ์อยู่แล้ว ระบบจะต่ออายุให้ต่อจากวันหมดอายุเดิม", back=reverse("dashboard:enrollment_list"))


@staff_required
def enrollment_extend(request, enrollment_id):
    enr = get_object_or_404(Enrollment.objects.select_related("user", "course"), pk=enrollment_id)
    form = ExtendForm(request.POST or None)
    return modal_form(request, form, save=lambda f: enrollment_service.extend(enr, request, add_days=f.cleaned_data.get("add_days"), expires_on=f.cleaned_data.get("expires_on")),
                      title="ปรับวันหมดอายุ", ok_message="ปรับวันหมดอายุแล้ว",
                      intro=f"{enr.user.full_name} · {enr.course.title} · หมดอายุ {timezone.localtime(enr.expires_at):%d/%m/%Y}",
                      back=reverse("dashboard:enrollment_list"))


@json_action
def enrollment_revoke(request, enrollment_id):
    return enrollment_service.revoke(get_object_or_404(Enrollment.objects.select_related("user", "course"), pk=enrollment_id), request)


@json_action
def enrollment_restore(request, enrollment_id):
    return enrollment_service.restore(get_object_or_404(Enrollment.objects.select_related("user", "course"), pk=enrollment_id), request)


@json_action
def enrollment_remind(request, enrollment_id):
    """ส่งอีเมลเตือนต่ออายุรายคน (เข้า Celery ไม่ค้าง request)"""
    if not reminder_service.queue_expiry_reminders([enrollment_id]):
        raise ActionError("ไม่พบสิทธิ์เรียนนี้")
    return "ส่งอีเมลเตือนแล้ว"


@json_action
def enrollment_bulk(request):
    body = json.loads(request.body or "{}")
    ids = [int(i) for i in body.get("ids", []) if str(i).isdigit()]
    if not ids:
        raise ActionError("ยังไม่ได้เลือกรายการ")
    if body.get("action") != "remind":
        raise ActionError("คำสั่งไม่ถูกต้อง")
    n = reminder_service.queue_expiry_reminders(ids)
    return f"ส่งอีเมลเตือน {n} รายการแล้ว"

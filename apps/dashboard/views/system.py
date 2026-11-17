"""หลังบ้าน: ภาพรวม · ผู้ดูแลระบบ · ตั้งค่า · ประวัติการแก้ไข · ถังขยะ · รายงาน"""
from django.contrib import messages
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.accounts.forms import AdminUserForm
from apps.accounts.models import User
from apps.accounts.services import account_service
from apps.core.decorators import staff_required
from apps.core.models import AuditLog
from apps.core.services import audit_service, settings_service
from apps.dashboard.crud import json_action, modal_form
from apps.dashboard.forms import ReportForm, SiteSettingsForm
from apps.dashboard.models import ReportExport
from apps.dashboard.selectors import stats_selector
from apps.dashboard.selectors.list_params import paginate
from apps.dashboard.services import trash_service
from apps.dashboard.tasks import generate_report_task


@staff_required
def overview(request):
    return render(request, "dashboard/overview.html", {"s": stats_selector.overview(30)})


# ---------- ผู้ดูแลระบบ ----------
@staff_required
def admin_list(request):
    qs = User.objects.filter(is_staff=True).only("id", "full_name", "email", "phone", "is_active", "last_login", "date_joined")
    ls = paginate(request, qs, search=("full_name", "email"), sorts={"name": ("full_name",), "login": ("last_login",)}, default_sort="name", per_page=50)
    return render(request, "dashboard/admin_list.html", {"ls": ls})


@staff_required
def admin_form(request, user_id=None):
    user = get_object_or_404(User, pk=user_id, is_staff=True) if user_id else None
    form = AdminUserForm(request.POST or None, instance=user, creating=user is None)
    out = {}

    def save(f):
        if user:
            account_service.update_by_admin(f, request)
        else:
            out["user"], out["pwd"] = account_service.create_by_admin(f, request, staff=True)

    resp = modal_form(request, form, save=save, title="แก้ไขแอดมิน" if user else "เพิ่มแอดมิน", ok_message="บันทึกแล้ว",
                      intro="แอดมินทุกคนมีสิทธิ์เท่ากัน ทำได้ทุกอย่างในหลังบ้าน" if not user else "", back=reverse("dashboard:admin_list"))
    if out and resp.status_code == 200 and request.headers.get("X-Requested-With") == "fetch":
        from django.http import JsonResponse

        return JsonResponse({"ok": True, "message": f"สร้างแอดมินแล้ว — รหัสผ่านชั่วคราว: {out['pwd']} (แจ้งผู้ใช้ให้เปลี่ยนเอง)"})
    return resp


@json_action
def admin_toggle(request, user_id):
    return account_service.set_active(get_object_or_404(User, pk=user_id, is_staff=True), request)


# ---------- ตั้งค่าเว็บ ----------
@staff_required
def site_settings(request):
    form = SiteSettingsForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        old = {k: settings_service.get(k) for k in settings_service.EDITABLE}
        settings_service.save_many(form.cleaned_data)
        changes = {k: [old[k], v] for k, v in form.cleaned_data.items() if old.get(k) != v}
        audit_service.log(request=request, action="update", model="SiteSetting", label="ตั้งค่าเว็บ", changes=changes)
        messages.success(request, "บันทึกการตั้งค่าแล้ว")
        return redirect("dashboard:site_settings")
    return render(request, "dashboard/site_settings.html", {"form": form, "secrets": settings_service.secret_status()})


# ---------- ประวัติการแก้ไข ----------
@staff_required
def audit_list(request):
    ls = paginate(
        request, AuditLog.objects.select_related("user").only("id", "action", "model", "object_id", "object_repr", "changes", "actor_label", "created_at", "ip", "user__full_name"),
        search=("object_repr", "user__full_name", "actor_label"), filters={"model": "model", "action": "action"},
        sorts={"time": ("created_at", "id")}, default_sort="-time", per_page=30,
    )
    models = list(AuditLog.objects.order_by().values_list("model", flat=True).distinct())
    actions = list(AuditLog.objects.order_by().values_list("action", flat=True).distinct())
    return render(request, "dashboard/audit_list.html", {
        "ls": ls, "filters_ui": [("model", "ข้อมูล", [(m, m) for m in models]), ("action", "การกระทำ", [(a, a) for a in actions])],
    })


# ---------- ถังขยะ ----------
@staff_required
def trash_list(request):
    return render(request, "dashboard/trash.html", {"items": trash_service.list_trash()})


@json_action
def trash_restore(request, kind, obj_id):
    return trash_service.restore(kind, obj_id, request)


@json_action
def trash_purge(request, kind, obj_id):
    return trash_service.purge(kind, obj_id, request)


# ---------- รายงาน ----------
@staff_required
def exports(request):
    form = ReportForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        export = ReportExport.objects.create(requested_by=request.user, **form.cleaned_data)
        audit_service.log(request=request, action="export", obj=export, label=f"รายงาน {export.get_kind_display()} ({export.fmt})")
        generate_report_task.delay(export.pk)
        messages.info(request, "กำลังสร้างรายงาน เสร็จแล้วจะขึ้นปุ่มดาวน์โหลด")
        return redirect("dashboard:exports")
    items = ReportExport.objects.only("id", "kind", "fmt", "status", "error", "created_at", "date_from", "date_to")[:20]
    return render(request, "dashboard/exports.html", {"form": form, "items": items})


@staff_required
def export_status(request):
    from django.http import JsonResponse

    ids = [int(i) for i in request.GET.get("ids", "").split(",") if i.isdigit()]
    return JsonResponse({"items": list(ReportExport.objects.filter(pk__in=ids).values("id", "status", "error"))})


@staff_required
def export_download(request, export_id):
    export = get_object_or_404(ReportExport, pk=export_id, status=ReportExport.Status.DONE)
    return FileResponse(export.file.open("rb"), as_attachment=True, filename=export.file.name.split("/")[-1])

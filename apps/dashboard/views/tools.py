"""หลังบ้าน: เครื่องมือ — ส่งอีเมลประกาศ · นำเข้านักเรียนจาก CSV"""
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render

from apps.accounts.services import import_service
from apps.core.decorators import staff_required
from apps.core.exceptions import ActionError
from apps.core.models import AuditLog
from apps.dashboard.forms import BroadcastForm, StudentImportForm
from apps.notifications.services import broadcast_service


@staff_required
def broadcast(request):
    """เขียนครั้งเดียว ส่งถึงนักเรียนทั้งกลุ่ม — กด "ส่งทดสอบ" ไปอีเมลตัวเองก่อนได้"""
    targets = broadcast_service.targets()
    form = BroadcastForm(request.POST or None, targets=targets)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            if request.POST.get("do") == "test":
                messages.success(request, broadcast_service.send_test(request.user, d["subject"], d["message"]))
                return render(request, "dashboard/broadcast.html", {"form": form, "history": _history()})
            n = broadcast_service.send(d["target"], d["subject"], d["message"], request)
            messages.success(request, f"กำลังส่งอีเมลถึง {n:,} คนในเบื้องหลัง (ใช้เวลาสักครู่ตามจำนวนผู้รับ)")
            return redirect("dashboard:broadcast")
        except ActionError as exc:
            form.add_error(None, str(exc))
    return render(request, "dashboard/broadcast.html", {"form": form, "history": _history()})


def _history():
    return AuditLog.objects.filter(action="broadcast").select_related("user").order_by("-created_at")[:10]


@staff_required
def student_import(request):
    form = StudentImportForm(request.POST or None, request.FILES or None)
    result = None
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        course = d["course"]
        try:
            result = import_service.import_students(
                d["file"], course=course, days=d["days"] or (course.access_days if course else None),
                send_email=d["send_email"], request=request,
            )
        except ActionError as exc:
            form.add_error("file", str(exc))
    return render(request, "dashboard/student_import.html", {"form": form, "result": result})


@staff_required
def student_import_template(request):
    resp = HttpResponse("﻿" + import_service.TEMPLATE_CSV, content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="letmehelp-students-template.csv"'
    return resp

"""ขอรายงาน: บันทึกคำขอ + audit แล้วส่งให้ Celery สร้างไฟล์ (สร้าง PDF/Excel ใน request ไม่ได้ — กฎข้อ 3)"""
from django.db import transaction

from apps.core.services import audit_service
from apps.dashboard.models import ReportExport
from apps.dashboard.tasks import generate_report_task


def request_export(*, data: dict, request) -> ReportExport:
    export = ReportExport.objects.create(requested_by=request.user, **data)
    audit_service.log(request=request, action="export", obj=export, label=f"รายงาน {export.get_kind_display()} ({export.fmt})")
    # ส่งงานหลัง commit เท่านั้น: worker จะไม่เจอแถวที่ยังไม่ถูกบันทึก
    transaction.on_commit(lambda: generate_report_task.delay(export.pk))
    return export


def recent_exports(limit: int = 20):
    return ReportExport.objects.only("id", "kind", "fmt", "status", "error", "created_at", "date_from", "date_to")[:limit]

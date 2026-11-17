"""สร้างไฟล์รายงาน Excel / PDF (เรียกจาก Celery task เท่านั้น ห้ามเรียกใน request)"""
import io
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from apps.dashboard.models import ReportExport
from apps.dashboard.selectors import stats_selector
from apps.payments.selectors import payment_selector

_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Tahoma.ttf",  # macOS
    "/usr/share/fonts/truetype/tlwg/Loma.ttf",  # Linux: fonts-thai-tlwg
    "/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf",
    "C:/Windows/Fonts/tahoma.ttf",
]


def _fmt(v):
    if v is None:
        return ""
    if hasattr(v, "astimezone"):
        return timezone.localtime(v).strftime("%d/%m/%Y %H:%M")
    return v


def _dataset(export: ReportExport):
    if export.kind == ReportExport.Kind.SALES:
        headers = ["เลขออเดอร์", "วันที่ชำระ", "ชื่อ", "อีเมล", "เบอร์โทร", "คอร์ส", "ยอด (บาท)", "ต่ออายุ"]
        rows = [
            [r[0], _fmt(r[1]), r[2], r[3], r[4], r[5], float(r[6]), "ใช่" if r[7] else ""]
            for r in payment_selector.paid_orders_for_export(export.date_from, export.date_to)
        ]
        return "รายงานยอดขาย", headers, rows
    if export.kind == ReportExport.Kind.ORDERS:
        from apps.payments.models import Order

        qs = Order.objects.select_related("user", "course").order_by("-created_at")
        if export.date_from:
            qs = qs.filter(created_at__date__gte=export.date_from)
        if export.date_to:
            qs = qs.filter(created_at__date__lte=export.date_to)
        headers = ["เลขออเดอร์", "วันที่สั่ง", "ชื่อ", "อีเมล", "คอร์ส", "แพ็กเกจ", "ยอด (บาท)", "สถานะ", "ที่มา"]
        rows = [[o.pk, _fmt(o.created_at), o.user.full_name, o.user.email, o.course.title, o.package_label, float(o.amount), o.get_status_display(), o.get_source_display()] for o in qs]
        return "รายงานออเดอร์", headers, rows
    if export.kind == ReportExport.Kind.EXPIRING:
        from datetime import timedelta

        from django.utils import timezone

        from apps.enrollments.models import Enrollment

        now = timezone.now()
        qs = Enrollment.objects.filter(status="active", expires_at__gt=now, expires_at__lte=now + timedelta(days=30)).select_related("user", "course").order_by("expires_at")
        headers = ["ชื่อ", "อีเมล", "เบอร์โทร", "คอร์ส", "หมดอายุ", "เหลือ (วัน)"]
        rows = [[e.user.full_name, e.user.email, e.user.phone, e.course.title, _fmt(e.expires_at), (e.expires_at - now).days] for e in qs]
        return "รายงานสิทธิ์ใกล้หมดอายุ", headers, rows
    headers = ["ชื่อ", "อีเมล", "เบอร์โทร", "คอร์ส", "เริ่มเรียน", "หมดอายุ", "สถานะ"]
    rows = [
        [r[0], r[1], r[2], r[3], _fmt(r[4]), _fmt(r[5]), r[6]]
        for r in stats_selector.students_for_export(export.date_from, export.date_to)
    ]
    return "รายงานนักเรียน/การสมัครเรียน", headers, rows


def _xlsx(title, headers, rows) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "report"
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True)
    for r in rows:
        ws.append(r)
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = min(40, max(10, max(len(str(c.value or "")) for c in col) + 2))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _pdf(title, headers, rows) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

    font_path = next((p for p in [settings.PDF_FONT_PATH, *_FONT_CANDIDATES] if p and Path(p).exists()), None)
    if font_path is None:
        raise RuntimeError("ไม่พบฟอนต์ไทยสำหรับ PDF — ตั้งค่า PDF_FONT_PATH ใน .env")
    pdfmetrics.registerFont(TTFont("TH", font_path))

    style = ParagraphStyle("t", fontName="TH", fontSize=8, leading=10)
    head = ParagraphStyle("h", fontName="TH", fontSize=14, leading=18)
    data = [[Paragraph(str(h), style) for h in headers]] + [
        [Paragraph(str(c), style) for c in row] for row in rows
    ]
    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f3f5")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#ced4da")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24).build(
        [Paragraph(f"{settings.SITE_NAME} — {title}", head), Paragraph(f"สร้างเมื่อ {timezone.localtime():%d/%m/%Y %H:%M}", style), table]
    )
    return buf.getvalue()


def build_report(export_id: int) -> None:
    export = ReportExport.objects.get(pk=export_id)
    try:
        title, headers, rows = _dataset(export)
        content = _xlsx(title, headers, rows) if export.fmt == ReportExport.Format.XLSX else _pdf(title, headers, rows)
        name = f"{export.kind}-{timezone.localtime():%Y%m%d-%H%M%S}.{export.fmt}"
        export.file.save(name, ContentFile(content), save=False)
        export.status = ReportExport.Status.DONE
        export.error = ""
    except Exception as exc:  # noqa: BLE001 — เก็บเหตุผลให้แอดมินเห็น
        export.status = ReportExport.Status.FAILED
        export.error = str(exc)[:255]
    export.save()

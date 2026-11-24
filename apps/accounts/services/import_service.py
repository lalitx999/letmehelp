"""นำเข้านักเรียนจากไฟล์ CSV (หลังบ้าน) — สร้างบัญชี + มอบสิทธิ์คอร์ส (ไม่บังคับ) + ส่งลิงก์ตั้งรหัสผ่าน (ไม่บังคับ)

- บัญชีใหม่ยังไม่มีรหัสผ่าน (ไม่ต้องสุ่ม/แฮช จึงเร็ว) นักเรียนตั้งเองจากลิงก์ในอีเมล หรือหน้า "ลืมรหัสผ่าน"
- อีเมลที่มีบัญชีอยู่แล้ว: ไม่แก้ข้อมูลเดิม แค่มอบสิทธิ์คอร์สให้ (ถ้าเลือกคอร์ส)
- แถวที่ผิดข้ามไปแถวเดียว แถวอื่นยังนำเข้าได้ และสรุปว่าแถวไหนผิดเพราะอะไร
"""
import csv
import io
import re
from datetime import datetime

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User, phone_validator
from apps.core.exceptions import ActionError
from apps.core.services import audit_service
from apps.enrollments.models import Enrollment
from apps.enrollments.services import enrollment_service

MAX_ROWS = 2000
MAX_BYTES = 2 * 1024 * 1024
# หัวคอลัมน์ที่รับได้ (ไม่สนตัวพิมพ์/ช่องว่าง)
COLUMNS = {
    "name": ("ชื่อ", "ชื่อ-นามสกุล", "ชื่อนามสกุล", "name", "full_name", "fullname"),
    "email": ("อีเมล", "อีเมล์", "email", "e-mail"),
    "phone": ("เบอร์", "เบอร์โทร", "เบอร์โทรศัพท์", "โทรศัพท์", "phone", "tel", "mobile"),
    "expires": ("วันหมดอายุ", "หมดอายุ", "expires", "expires_on", "expiry"),
}
TEMPLATE_CSV = "ชื่อ-นามสกุล,อีเมล,เบอร์โทร,วันหมดอายุ\nสมชาย ใจดี,somchai@example.com,0812345678,2027-12-31\n"


def _decode(raw: bytes) -> str:
    # Excel บน Windows ภาษาไทยมักบันทึก CSV เป็น TIS-620 (cp874) ส่วน Mac/Google Sheets เป็น UTF-8
    for enc in ("utf-8-sig", "cp874"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ActionError("อ่านไฟล์ไม่ได้ กรุณาบันทึกเป็น CSV (UTF-8)")


def _header_map(header):
    norm = [re.sub(r"\s+", "", h or "").lower() for h in header]
    out = {}
    for key, names in COLUMNS.items():
        for i, h in enumerate(norm):
            if h in names:
                out[key] = i
                break
    missing = [k for k in ("name", "email") if k not in out]
    if missing:
        raise ActionError("ไม่พบคอลัมน์ " + " และ ".join({"name": "ชื่อ-นามสกุล", "email": "อีเมล"}[k] for k in missing) + " ในแถวแรกของไฟล์")
    return out


def _phone(v: str) -> str:
    d = re.sub(r"\D", "", v or "")
    if d.startswith("66") and len(d) in (11, 12):  # +66 81 234 5678
        d = "0" + d[2:]
    if len(d) in (8, 9) and not d.startswith("0"):  # Excel ตัดเลข 0 ข้างหน้าทิ้ง
        d = "0" + d
    return d


def _date(v: str):
    v = (v or "").strip()
    if not v:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y"):
        try:
            d = datetime.strptime(v, fmt).date()
        except ValueError:
            continue
        return d.replace(year=d.year - 543) if d.year > 2400 else d  # ปี พ.ศ.
    raise ValueError("วันหมดอายุไม่ถูกต้อง (ใช้ 2027-12-31 หรือ 31/12/2027)")


def parse(file):
    """คืน [(เลขแถว, {name, email, phone, expires})] — ตรวจรูปแบบไฟล์ ไม่แตะฐานข้อมูล"""
    if not file.name.lower().endswith(".csv"):
        raise ActionError("รองรับเฉพาะไฟล์ .csv (ใน Excel: บันทึกเป็น → CSV UTF-8)")
    if file.size > MAX_BYTES:
        raise ActionError("ไฟล์ใหญ่เกิน 2MB")
    reader = csv.reader(io.StringIO(_decode(file.read())))
    rows = [r for r in reader if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise ActionError("ไม่มีข้อมูลนักเรียนในไฟล์ (แถวแรกต้องเป็นหัวคอลัมน์)")
    if len(rows) - 1 > MAX_ROWS:
        raise ActionError(f"นำเข้าได้ครั้งละไม่เกิน {MAX_ROWS:,} คน")
    cols = _header_map(rows[0])
    get = lambda r, k: r[cols[k]].strip() if k in cols and cols[k] < len(r) else ""  # noqa: E731
    return [(i, {k: get(r, k) for k in COLUMNS}) for i, r in enumerate(rows[1:], start=2)]


def _grant(user, course, days, expires_on, request):
    if expires_on:
        exp = timezone.make_aware(datetime.combine(expires_on, datetime.max.time().replace(microsecond=0)))
        now = timezone.now()
        status = Enrollment.Status.ACTIVE if exp > now else Enrollment.Status.EXPIRED
        Enrollment.objects.update_or_create(
            user=user, course=course,
            defaults={"expires_at": exp, "status": status, "source": "manual", "granted_by": request.user, "note": "นำเข้าจาก CSV"},
            create_defaults={"started_at": now, "expires_at": exp, "status": status, "source": "manual", "granted_by": request.user, "note": "นำเข้าจาก CSV"},
        )
    else:
        enrollment_service.grant_or_extend(user=user, course=course, days=days, source="manual", granted_by=request.user, note="นำเข้าจาก CSV")


def import_students(file, *, course=None, days=None, send_email=False, request) -> dict:
    rows = parse(file)
    result = {"total": len(rows), "created": 0, "existing": 0, "granted": 0, "emailed": 0, "errors": []}
    seen = set()
    existing = {u.email: u for u in User.objects.filter(email__in=[r["email"].lower() for _, r in rows])}
    new_ids = []
    for line, r in rows:
        email = r["email"].lower()
        try:
            if not r["name"]:
                raise ValueError("ไม่มีชื่อ")
            if len(r["name"]) > 150:
                raise ValueError("ชื่อยาวเกิน 150 ตัวอักษร")
            try:
                validate_email(email)
            except ValidationError:
                raise ValueError("อีเมลไม่ถูกต้อง")
            if email in seen:
                raise ValueError("อีเมลซ้ำกับแถวก่อนหน้าในไฟล์")
            seen.add(email)
            expires_on = _date(r["expires"])
            user = existing.get(email)
            with transaction.atomic():
                if user is None:
                    phone = _phone(r["phone"])
                    try:
                        phone_validator(phone)
                    except ValidationError:
                        raise ValueError("เบอร์โทรไม่ถูกต้อง (ต้องเป็น 0 ตามด้วยตัวเลข 8–9 หลัก)")
                    user = User.objects.create_user(email=email, password=None, full_name=r["name"], phone=phone,
                                                    admin_note=f"นำเข้าจาก CSV {timezone.localdate():%d/%m/%Y}")
                    result["created"] += 1
                    new_ids.append(user.pk)
                elif user.is_staff:
                    raise ValueError("อีเมลนี้เป็นบัญชีแอดมิน")
                else:
                    result["existing"] += 1
                if course is not None:
                    _grant(user, course, days, expires_on, request)
                    result["granted"] += 1
        except ValueError as exc:
            result["errors"].append((line, email or "-", str(exc)))
    if send_email and new_ids:
        from apps.notifications.tasks import send_set_password_email

        for pk in new_ids:
            send_set_password_email.delay(pk)
        result["emailed"] = len(new_ids)
    audit_service.log(request=request, action="import", model="User", label=f"นำเข้านักเรียน {result['created']} คนใหม่",
                      changes={k: v for k, v in result.items() if k != "errors"} | {"course": course.title if course else "", "errors": len(result["errors"])})
    return result


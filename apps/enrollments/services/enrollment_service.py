from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import ActionError
from apps.core.services import audit_service
from apps.enrollments.models import Enrollment


@transaction.atomic
def grant_or_extend(*, user, course, days: int | None = None, source: str = "purchase", granted_by=None, note: str = "") -> Enrollment:
    """เปิดสิทธิ์เรียน หรือต่ออายุถ้าเคยซื้อแล้ว
    ต่ออายุขณะยังไม่หมด → นับต่อจากวันหมดอายุเดิม (ไม่เสียวันที่เหลือ)"""
    now = timezone.now()
    enrollment = Enrollment.objects.select_for_update().filter(user=user, course=course).first()
    delta = timedelta(days=days or course.access_days)  # days = อายุของแพ็กเกจที่ซื้อ
    if enrollment is None:
        return Enrollment.objects.create(
            user=user, course=course, started_at=now, expires_at=now + delta, status=Enrollment.Status.ACTIVE,
            source=source, granted_by=granted_by, note=note,
        )
    base = max(now, enrollment.expires_at)
    enrollment.expires_at = base + delta
    enrollment.status = Enrollment.Status.ACTIVE
    fields = ["expires_at", "status"]
    if source != "purchase":
        enrollment.source, enrollment.granted_by, enrollment.note = source, granted_by, note or enrollment.note
        fields += ["source", "granted_by", "note"]
    enrollment.save(update_fields=fields)
    return enrollment


def expire_overdue() -> int:
    """ปิดสิทธิ์ที่หมดอายุแล้วแบบ bulk update คำสั่งเดียว"""
    return Enrollment.objects.filter(status=Enrollment.Status.ACTIVE, expires_at__lte=timezone.now()).update(
        status=Enrollment.Status.EXPIRED
    )


# ---- งานของแอดมิน -------------------------------------------------------------------
def grant_manual(*, user, course, days: int, source: str, note: str, request) -> Enrollment:
    enrollment = grant_or_extend(user=user, course=course, days=days, source=source, granted_by=request.user, note=note)
    audit_service.log(request=request, action="grant", obj=enrollment,
                      label=f"{user.full_name} → {course.title}", changes={"days": days, "source": source, "note": note})
    return enrollment


def extend(enrollment: Enrollment, request, *, add_days: int | None = None, expires_on=None) -> str:
    """ต่ออายุ +N วัน (นับจากวันหมดอายุเดิมหรือวันนี้ แล้วแต่อันไหนไกลกว่า) หรือกำหนดวันหมดอายุเอง"""
    old = enrollment.expires_at
    if add_days:
        enrollment.expires_at = max(timezone.now(), enrollment.expires_at) + timedelta(days=add_days)
    elif expires_on:
        enrollment.expires_at = timezone.make_aware(datetime.combine(expires_on, datetime.max.time().replace(microsecond=0)))
    else:
        raise ActionError("ระบุจำนวนวัน หรือวันหมดอายุ")
    if enrollment.expires_at > timezone.now():
        enrollment.status = Enrollment.Status.ACTIVE
    enrollment.save(update_fields=["expires_at", "status"])
    audit_service.log(request=request, action="extend", obj=enrollment, label=f"{enrollment.user.full_name} → {enrollment.course.title}",
                      changes={"expires_at": [old.isoformat(), enrollment.expires_at.isoformat()]})
    return "ปรับวันหมดอายุแล้ว"


def revoke(enrollment: Enrollment, request) -> str:
    enrollment.status = Enrollment.Status.CANCELLED
    enrollment.save(update_fields=["status"])
    audit_service.log(request=request, action="revoke", obj=enrollment, label=f"{enrollment.user.full_name} → {enrollment.course.title}")
    return "ยกเลิกสิทธิ์เรียนแล้ว (กู้คืนได้)"


def restore(enrollment: Enrollment, request) -> str:
    enrollment.status = Enrollment.Status.ACTIVE if enrollment.expires_at > timezone.now() else Enrollment.Status.EXPIRED
    enrollment.save(update_fields=["status"])
    audit_service.log(request=request, action="restore", obj=enrollment, label=f"{enrollment.user.full_name} → {enrollment.course.title}")
    return "กู้คืนสิทธิ์เรียนแล้ว"


LIFETIME_DAYS = 36500  # "ตลอดชีพ" = 100 ปี (หน้าเว็บแสดงเป็นตลอดชีพเมื่อปีหมดอายุ > 2100)


def _end_of_day(d):
    return timezone.make_aware(datetime.combine(d, datetime.max.time().replace(microsecond=0)))


@transaction.atomic
def set_access(user, request, rows) -> int:
    """หน้าต่างนักเรียนในหลังบ้าน: ตั้งสิทธิ์ทุกคอร์สทีเดียว
    rows = [(course, เปิดสิทธิ์?, วันหมดอายุ date|None)] — ทำเฉพาะแถวที่เปลี่ยนจริง คืนจำนวนแถวที่เปลี่ยน
    เปิด + ยังไม่เคยมี → มอบสิทธิ์ · เปิด + มีอยู่ → ปรับวัน/กู้คืน · ปิด → ยกเลิกสิทธิ์ (กู้คืนได้ ไม่ลบประวัติ)"""
    current = {e.course_id: e for e in Enrollment.objects.select_for_update().filter(user=user)}
    now = timezone.now()
    changed = 0
    for course, on, expires_on in rows:
        enr = current.get(course.pk)
        label = f"{user.full_name} → {course.title}"
        if on:
            expires_at = _end_of_day(expires_on) if expires_on else now + timedelta(days=course.access_days)
            status = Enrollment.Status.ACTIVE if expires_at > now else Enrollment.Status.EXPIRED
            if enr is None:
                enr = Enrollment.objects.create(user=user, course=course, started_at=now, expires_at=expires_at, status=status,
                                                source="manual", granted_by=request.user)
                audit_service.log(request=request, action="grant", obj=enr, label=label, changes={"expires_at": expires_at.isoformat()})
                changed += 1
            elif enr.status == Enrollment.Status.CANCELLED or enr.expires_at.date() != expires_at.date() or enr.status != status:
                old = enr.expires_at
                enr.expires_at, enr.status = expires_at, status
                enr.save(update_fields=["expires_at", "status"])
                audit_service.log(request=request, action="extend", obj=enr, label=label,
                                  changes={"expires_at": [old.isoformat(), expires_at.isoformat()]})
                changed += 1
        elif enr is not None and enr.status != Enrollment.Status.CANCELLED:
            enr.status = Enrollment.Status.CANCELLED
            enr.save(update_fields=["status"])
            audit_service.log(request=request, action="revoke", obj=enr, label=label)
            changed += 1
    return changed

"""ถังขยะ: กู้คืน / ลบถาวร (บล็อกถ้ายังมีข้อมูลอื่นผูกอยู่)"""
from django.db import transaction

from apps.core.exceptions import ActionError
from apps.core.services import audit_service
from apps.courses.models import Category, Course, Lesson, Section

KINDS = {"course": Course, "category": Category, "section": Section, "lesson": Lesson}
LABELS = {"course": "คอร์ส", "category": "หมวด", "section": "บท", "lesson": "คลิป"}


def _get(kind: str, pk: int):
    model = KINDS.get(kind)
    if model is None:
        raise ActionError("ประเภทข้อมูลไม่ถูกต้อง")
    obj = model.all_objects.filter(pk=pk, deleted_at__isnull=False).first()
    if obj is None:
        raise ActionError("ไม่พบรายการในถังขยะ")
    return obj


def list_trash() -> list[dict]:
    rows = []
    for kind, model in KINDS.items():
        for o in model.all_objects.dead().order_by("-deleted_at")[:100]:
            rows.append({"kind": kind, "label": LABELS[kind], "id": o.pk, "title": str(o), "deleted_at": o.deleted_at})
    return sorted(rows, key=lambda r: r["deleted_at"], reverse=True)


@transaction.atomic
def restore(kind: str, pk: int, request) -> str:
    obj = _get(kind, pk)
    if kind == "lesson" and Section.all_objects.filter(pk=obj.section_id, deleted_at__isnull=False).exists():
        raise ActionError("บทของคลิปนี้ยังอยู่ในถังขยะ กู้คืนบทก่อน")
    if kind == "section":
        # กู้คืนคลิปที่ถูกลบพร้อมบท (เวลาลบเดียวกัน)
        Lesson.all_objects.filter(section=obj, deleted_at=obj.deleted_at).update(deleted_at=None)
    if kind == "course":
        pass  # กู้คืนเป็นฉบับร่าง (ไม่เผยแพร่เอง)
    obj.deleted_at = None
    obj.save(update_fields=["deleted_at"])
    audit_service.log(request=request, action="restore", obj=obj)
    return f"กู้คืน{LABELS[kind]}แล้ว" + (" (เป็นฉบับร่าง)" if kind == "course" else "")


@transaction.atomic
def purge(kind: str, pk: int, request) -> str:
    obj = _get(kind, pk)
    if kind == "course" and (obj.enrollments.exists() or obj.orders.exists()):
        raise ActionError("ลบถาวรไม่ได้: คอร์สนี้ยังมีนักเรียน/ออเดอร์ผูกอยู่ (เก็บไว้ในถังขยะต่อไป)")
    if kind == "category" and Course.all_objects.filter(category=obj).exists():
        raise ActionError("ลบถาวรไม่ได้: ยังมีคอร์สในหมวดนี้ (รวมที่อยู่ในถังขยะ)")
    label = f"{LABELS[kind]}: {obj}"
    audit_service.log(request=request, action="purge", model=obj.__class__.__name__, object_id=obj.pk, label=label)
    if kind == "section":
        for att in __import__("apps.courses.models", fromlist=["LessonAttachment"]).LessonAttachment.objects.filter(lesson__section=obj):
            att.file.delete(save=False)
    obj.delete()
    return f"ลบ{LABELS[kind]}ถาวรแล้ว"

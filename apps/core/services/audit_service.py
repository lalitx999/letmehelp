"""บันทึกประวัติการแก้ไข — เรียกจาก service/view ที่เขียนข้อมูล"""
from apps.core.models import AuditLog


def _ip(request):
    return request.META.get("REMOTE_ADDR") if request is not None else None


def log(*, action: str, request=None, user=None, obj=None, model: str = "", object_id="", label: str = "",
        changes: dict | None = None, actor_label: str = "") -> AuditLog:
    """user/request ให้อย่างใดอย่างหนึ่ง (ไม่มี = ระบบ ให้ใส่ actor_label); obj ใช้ดึงชื่อโมเดลและรหัส"""
    actor = user or (request.user if request is not None and request.user.is_authenticated else None)
    if obj is not None:
        model = model or obj.__class__.__name__
        object_id = object_id or obj.pk
        label = label or str(obj)
    return AuditLog.objects.create(
        user=actor,
        actor_label=actor_label if actor is None else "",
        action=action,
        model=model,
        object_id=str(object_id or ""),
        object_repr=str(label)[:200],
        changes=changes or {},
        ip=_ip(request),
    )


def form_changes(form) -> dict:
    """{ฟิลด์: [ค่าเดิม, ค่าใหม่]} เฉพาะที่เปลี่ยนจริง (ข้อความยาวตัดที่ 120 ตัวอักษร ไม่เก็บรหัสผ่าน)"""
    out = {}
    for name in form.changed_data:
        if "password" in name:
            continue
        old, new = form.initial.get(name), form.cleaned_data.get(name)
        out[name] = [str(old)[:120] if old is not None else None, str(new)[:120] if new is not None else None]
    return out

import secrets

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.exceptions import ActionError
from apps.core.services import audit_service


def register_student(*, full_name: str, phone: str, email: str, password: str) -> User:
    """สร้างบัญชีนักเรียน (ไม่ใช่ staff)"""
    user = User.objects.create_user(
        email=email, password=password, full_name=full_name, phone=phone, terms_accepted_at=timezone.now()
    )
    from apps.notifications.tasks import notify_admins

    transaction.on_commit(lambda: notify_admins.delay(f"[สมัครใหม่] {full_name} · {email} · {phone}"))
    return user


def _temp_password() -> str:
    return secrets.token_urlsafe(9)


@transaction.atomic
def create_by_admin(form, request, *, staff: bool = False):
    """แอดมินสร้างบัญชี: ถ้าไม่ใส่รหัสผ่านจะสุ่มให้ — คืน (user, รหัสผ่านที่ตั้ง) เพื่อให้แอดมินแจ้งผู้ใช้"""
    data = form.cleaned_data
    password = data.get("password") or _temp_password()
    user = User.objects.create_user(
        email=data["email"], password=password, full_name=data["full_name"], phone=data["phone"],
        admin_note=data.get("admin_note", ""), is_staff=staff,
    )
    audit_service.log(request=request, action="create", obj=user, changes={"role": "admin" if staff else "student"})
    return user, password


def update_by_admin(form, request):
    user = form.save()
    audit_service.log(request=request, action="update", obj=user, changes=audit_service.form_changes(form))
    return user


def set_active(user: User, request, *, active: bool | None = None) -> str:
    """เปิด/ปิดบัญชี (ไม่ลบข้อมูล) — กันปิดบัญชีตัวเอง และกันปิดแอดมินคนสุดท้าย"""
    target = (not user.is_active) if active is None else active
    if not target and user.pk == request.user.pk:
        raise ActionError("ปิดบัญชีของตัวเองไม่ได้")
    if not target and user.is_staff and User.objects.filter(is_staff=True, is_active=True).exclude(pk=user.pk).count() == 0:
        raise ActionError("ต้องเหลือแอดมินที่ใช้งานได้อย่างน้อย 1 คน")
    user.is_active = target
    user.save(update_fields=["is_active"])
    audit_service.log(request=request, action="update", obj=user, changes={"is_active": [not target, target]})
    return "เปิดใช้งานบัญชีแล้ว" if target else "ปิดบัญชีแล้ว (ข้อมูลยังอยู่ ผู้ใช้ล็อกอินไม่ได้)"


def reset_password(user: User, request, new_password: str = "") -> str:
    password = new_password or _temp_password()
    user.set_password(password)
    user.save(update_fields=["password"])
    audit_service.log(request=request, action="reset_password", obj=user)
    return password

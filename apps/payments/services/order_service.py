from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import ActionError
from apps.core.services import audit_service
from apps.enrollments.models import Enrollment
from apps.enrollments.selectors.enrollment_selector import get_enrollment
from apps.enrollments.services import enrollment_service
from apps.payments.models import Order, PaymentSlip


def get_or_create_pending_order(*, user, course, package) -> Order:
    """ใช้ออเดอร์ที่ยังไม่จ่ายเดิมซ้ำ (กันออเดอร์ค้างเป็นร้อย) แล้วอัปเดตเป็นแพ็กเกจ/ราคาล่าสุดที่เลือก"""
    in_review = Order.objects.filter(user=user, course=course, status=Order.Status.REVIEWING).order_by("-created_at").first()
    if in_review:  # มีสลิปกำลังตรวจอยู่ — กลับมาดูสถานะของออเดอร์เดิม ไม่สร้างใหม่
        return in_review
    order = (
        Order.objects.filter(user=user, course=course, status__in=[Order.Status.PENDING, Order.Status.REJECTED])
        .order_by("-created_at")
        .first()
    )
    if order:
        order.amount = package.price
        order.duration_days = package.days
        order.package_label = package.label
        order.status = Order.Status.PENDING
        order.save(update_fields=["amount", "duration_days", "package_label", "status"])
        return order
    return Order.objects.create(
        user=user,
        course=course,
        amount=package.price,
        duration_days=package.days,
        package_label=package.label,
        is_renewal=get_enrollment(user, course.pk) is not None,
    )


@transaction.atomic
def submit_slip(*, order: Order, image) -> PaymentSlip:
    """บันทึกสลิป แล้วโยนงานตรวจเข้า Celery หลัง commit (ไม่ตรวจใน request)"""
    from apps.payments.tasks import verify_slip_task

    slip = PaymentSlip.objects.create(order=order, image=image)
    Order.objects.filter(pk=order.pk).update(status=Order.Status.REVIEWING)
    transaction.on_commit(lambda: verify_slip_task.delay(slip.pk))
    # แจ้ง Telegram (รูปสลิป) ทำใน verify_slip_task ก่อนเริ่มตรวจ เพื่อให้ลำดับข้อความถูกต้อง
    return slip


@transaction.atomic
def mark_paid(*, order_id: int, notify_admins: bool = True) -> Order:
    """ยืนยันว่าชำระแล้ว + เปิดสิทธิ์เรียน — idempotent (เรียกซ้ำได้ไม่เปิดสิทธิ์ซ้ำ)"""
    order = Order.objects.select_for_update().select_related("user", "course").get(pk=order_id)
    if order.status == Order.Status.PAID:
        return order
    order.status = Order.Status.PAID
    order.paid_at = timezone.now()
    order.save(update_fields=["status", "paid_at"])
    enrollment_service.grant_or_extend(user=order.user, course=order.course, days=order.duration_days or None)

    from apps.notifications import tasks as notify

    transaction.on_commit(lambda: notify.send_payment_success_email.delay(order.pk))
    if notify_admins:
        transaction.on_commit(
            lambda: notify.notify_admins.delay(f"✅ [ชำระแล้ว] ออเดอร์ #{order.pk}: {order.user.full_name} ซื้อ {order.course.title} ({order.amount:,.0f} บาท) — เปิดสิทธิ์เรียนแล้ว")
        )
    return order


@transaction.atomic
def approve_slip_manually(*, slip_id: int, admin, request=None) -> PaymentSlip:
    slip = PaymentSlip.objects.select_for_update().get(pk=slip_id)
    if slip.status == PaymentSlip.Status.VERIFIED:
        return slip
    slip.status = PaymentSlip.Status.VERIFIED
    slip.reviewed_by = admin
    slip.verified_at = timezone.now()
    slip.reason = "อนุมัติโดยแอดมิน"
    slip.save(update_fields=["status", "reviewed_by", "verified_at", "reason"])
    mark_paid(order_id=slip.order_id)
    audit_service.log(request=request, user=admin, action="approve", model="Order", object_id=slip.order_id, label=f"ออเดอร์ #{slip.order_id}")
    return slip


@transaction.atomic
def reject_slip_manually(*, slip_id: int, admin, reason: str, request=None) -> PaymentSlip:
    slip = PaymentSlip.objects.select_for_update().get(pk=slip_id)
    if slip.order.status == Order.Status.PAID:
        return slip
    slip.status = PaymentSlip.Status.REJECTED
    slip.reviewed_by = admin
    slip.reason = reason or "แอดมินปฏิเสธสลิป"
    slip.save(update_fields=["status", "reviewed_by", "reason"])
    Order.objects.filter(pk=slip.order_id).update(status=Order.Status.REJECTED)
    audit_service.log(request=request, user=admin, action="reject", model="Order", object_id=slip.order_id, label=f"ออเดอร์ #{slip.order_id}", changes={"reason": slip.reason})
    return slip


# ---- งานของแอดมินกับออเดอร์ ---------------------------------------------------------
UNPAID = (Order.Status.PENDING, Order.Status.REVIEWING, Order.Status.REJECTED)


@transaction.atomic
def create_manual_order(*, user, course, amount, days: int, note: str, paid: bool, request) -> Order:
    """แอดมินสร้างออเดอร์ให้นักเรียน (เช่น โอนนอกระบบ/เงินสด) — เลือกให้ชำระแล้วและเปิดสิทธิ์ทันทีได้"""
    order = Order.objects.create(
        user=user, course=course, amount=amount, duration_days=days, package_label="กำหนดเอง",
        source=Order.Source.MANUAL, note=note, created_by=request.user, is_renewal=get_enrollment(user, course.pk) is not None,
    )
    audit_service.log(request=request, action="create", obj=order, label=f"ออเดอร์ #{order.pk}", changes={"amount": str(amount), "days": days, "paid": paid})
    if paid:
        mark_paid(order_id=order.pk)
    return order


def mark_paid_manually(order: Order, request) -> str:
    if order.status == Order.Status.PAID:
        raise ActionError("ออเดอร์นี้ชำระแล้ว")
    if order.status in (Order.Status.CANCELLED, Order.Status.REFUNDED):
        raise ActionError("ออเดอร์ที่ยกเลิก/คืนเงินแล้ว ทำเครื่องหมายว่าชำระไม่ได้")
    mark_paid(order_id=order.pk)
    audit_service.log(request=request, action="approve", obj=order, label=f"ออเดอร์ #{order.pk}", changes={"manual": True})
    return "ทำเครื่องหมายว่าชำระแล้วและเปิดสิทธิ์เรียนให้แล้ว"


def cancel_order(order: Order, request) -> str:
    if order.status not in UNPAID:
        raise ActionError("ยกเลิกได้เฉพาะออเดอร์ที่ยังไม่ชำระ (ถ้าชำระแล้วให้ใช้คืนเงิน)")
    Order.objects.filter(pk=order.pk).update(status=Order.Status.CANCELLED)
    audit_service.log(request=request, action="cancel", obj=order, label=f"ออเดอร์ #{order.pk}")
    return "ยกเลิกออเดอร์แล้ว"


@transaction.atomic
def refund_order(order: Order, request, *, revoke_access: bool, note: str = "") -> str:
    """ทำเครื่องหมายคืนเงิน (การโอนเงินคืนทำนอกระบบ) และเลือกเพิกถอนสิทธิ์เรียนของคอร์สนั้นได้"""
    if order.status != Order.Status.PAID:
        raise ActionError("คืนเงินได้เฉพาะออเดอร์ที่ชำระแล้ว")
    Order.objects.filter(pk=order.pk).update(status=Order.Status.REFUNDED, note=(note or order.note)[:300])
    if revoke_access:
        Enrollment.objects.filter(user_id=order.user_id, course_id=order.course_id).update(status=Enrollment.Status.CANCELLED)
    audit_service.log(request=request, action="refund", obj=order, label=f"ออเดอร์ #{order.pk}", changes={"revoke_access": revoke_access, "note": note})
    return "บันทึกการคืนเงินแล้ว" + (" และเพิกถอนสิทธิ์เรียนแล้ว" if revoke_access else "")


def resend_confirmation(order: Order, request) -> str:
    if order.status != Order.Status.PAID:
        raise ActionError("ส่งอีเมลยืนยันได้เฉพาะออเดอร์ที่ชำระแล้ว")
    from apps.notifications.tasks import send_payment_success_email

    send_payment_success_email.delay(order.pk)
    audit_service.log(request=request, action="resend_email", obj=order, label=f"ออเดอร์ #{order.pk}")
    return "ส่งอีเมลยืนยันแล้ว"

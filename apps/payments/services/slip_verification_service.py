"""ตรวจสลิปอัตโนมัติ: ยอดตรง + ผู้รับตรง + เลขอ้างอิงไม่ซ้ำ → อนุมัติและเปิดสิทธิ์เรียนทันที"""
import logging
import re

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.payments.models import Order, PaymentSlip

from . import order_service
from .easyslip_client import SlipData, SlipNotFound, verify_slip_image

logger = logging.getLogger(__name__)


def _norm(s: str) -> str:
    return re.sub(r"[\s.]", "", s or "").lower()


def _receiver_ok(data: SlipData) -> bool | None:
    """True = ตรง, False = ไม่ตรง, None = ตั้งค่าบัญชีรับเงินไม่ครบ (ตรวจเองไม่ได้)"""
    from apps.core.services import settings_service

    real_id = re.sub(r"\D", "", settings_service.get("PROMPTPAY_ID"))
    real_name = _norm(settings_service.get("PROMPTPAY_ACCOUNT_NAME"))
    if not real_id and not real_name:
        return None
    if real_name and any(real_name in _norm(n) or _norm(n) in real_name for n in data.receiver_names):
        return True
    if real_id:
        for masked in data.receiver_masked_ids:
            runs = [r for r in re.findall(r"\d+", masked) if len(r) >= 3]
            if runs and all(r in real_id for r in runs):
                return True
    return False


def _finish(slip_id, status, reason="", **fields):
    PaymentSlip.objects.filter(pk=slip_id).update(
        status=status, reason=reason[:255], verified_at=timezone.now(), **fields
    )


def mark_manual_review(slip_id: int, reason: str) -> None:
    _finish(slip_id, PaymentSlip.Status.MANUAL_REVIEW, reason)
    slip = PaymentSlip.objects.select_related("order__user").get(pk=slip_id)
    from apps.notifications.tasks import notify_admins

    notify_admins.delay(
        f"[สลิปรอตรวจ] ออเดอร์ #{slip.order_id} ({slip.order.user.full_name}) {slip.order.amount:,.0f} บาท — {reason}"
    )


def _notify_review(slip_id: int, reason: str) -> None:
    slip = PaymentSlip.objects.select_related("order__user").get(pk=slip_id)
    from apps.notifications.tasks import notify_admins

    notify_admins.delay(
        f"[สลิปรอตรวจ] ออเดอร์ #{slip.order_id} ({slip.order.user.full_name}) {slip.order.amount:,.0f} บาท — {reason}"
    )


def verify_slip(slip_id: int) -> str:
    """คืนสถานะสุดท้ายของสลิป"""
    slip = PaymentSlip.objects.select_related("order").get(pk=slip_id)
    if slip.status != PaymentSlip.Status.PENDING:
        return slip.status
    order = slip.order

    if not settings.EASYSLIP_API_KEY:
        mark_manual_review(slip_id, "ยังไม่ได้ตั้งค่า EasySlip")
        return PaymentSlip.Status.MANUAL_REVIEW

    with slip.image.open("rb") as fh:
        try:
            data = verify_slip_image(fh)
        except SlipNotFound as exc:
            _finish(slip_id, PaymentSlip.Status.REJECTED, "อ่านสลิปไม่ได้หรือไม่พบข้อมูล กรุณาอัปโหลดสลิปที่ชัดเจน")
            Order.objects.filter(pk=order.pk).update(status=Order.Status.REJECTED)
            logger.info("slip %s not found: %s", slip_id, exc)
            return PaymentSlip.Status.REJECTED

    raw = {"raw_response": data.raw, "verified_amount": data.amount}

    # สลิปที่ไม่มีเลขอ้างอิง ใช้กันสลิปซ้ำไม่ได้ → ให้แอดมินตรวจ
    if not data.trans_ref:
        _finish(slip_id, PaymentSlip.Status.MANUAL_REVIEW, "สลิปไม่มีเลขอ้างอิงธุรกรรม", **raw)
        _notify_review(slip_id, "สลิปไม่มีเลขอ้างอิง")
        return PaymentSlip.Status.MANUAL_REVIEW

    receiver = _receiver_ok(data)
    problems = []
    if data.amount != order.amount:
        problems.append(f"ยอดไม่ตรง (สลิป {data.amount} / ต้องชำระ {order.amount})")
    if receiver is False:
        problems.append("ผู้รับเงินไม่ตรงกับบัญชีของร้าน")
    if problems:
        # น่าสงสัย: บันทึก trans_ref (กันนำสลิปเดิมกลับมาใช้) แล้วส่งให้แอดมินตัดสินใจ เช่น โอนเกิน/โอนผิดบัญชี
        reason = " · ".join(problems)
        try:
            with transaction.atomic():
                _finish(slip_id, PaymentSlip.Status.MANUAL_REVIEW, reason, trans_ref=data.trans_ref, **raw)
        except IntegrityError:
            _finish(slip_id, PaymentSlip.Status.REJECTED, "สลิปนี้ถูกใช้งานแล้ว", **raw)
            Order.objects.filter(pk=order.pk).update(status=Order.Status.REJECTED)
            return PaymentSlip.Status.REJECTED
        _notify_review(slip_id, reason)
        return PaymentSlip.Status.MANUAL_REVIEW

    # ยอดตรง + เลขอ้างอิงไม่ซ้ำ (+ผู้รับตรงถ้าตั้งค่าบัญชีร้านไว้) → อนุมัติและเปิดสิทธิ์ทันที เหมือน ryu_new
    try:
        with transaction.atomic():
            _finish(slip_id, PaymentSlip.Status.VERIFIED, "", trans_ref=data.trans_ref, **raw)
    except IntegrityError:  # trans_ref ซ้ำ = สลิปเคยถูกใช้แล้ว
        _finish(slip_id, PaymentSlip.Status.REJECTED, "สลิปนี้ถูกใช้งานแล้ว", **raw)
        Order.objects.filter(pk=order.pk).update(status=Order.Status.REJECTED)
        return PaymentSlip.Status.REJECTED

    order_service.mark_paid(order_id=order.pk)
    from apps.core.services import audit_service

    audit_service.log(
        action="approve", model="Order", object_id=order.pk, label=f"ออเดอร์ #{order.pk}",
        actor_label="ระบบ (EasySlip)", changes={"amount": str(data.amount), "trans_ref": data.trans_ref},
    )
    return PaymentSlip.Status.VERIFIED

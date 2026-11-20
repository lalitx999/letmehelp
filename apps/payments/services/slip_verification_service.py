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


TITLES = ("นางสาว", "นาง", "นาย", "นส", "ดญ", "ดช", "miss", "mrs", "mr", "ms")


def _norm(s: str) -> str:
    return re.sub(r"[\s.]", "", s or "").lower()


def _name_key(s: str) -> str:
    """ตัดคำนำหน้าชื่อ: "น.ส. ศิตา ว" → "ศิตาว" (สลิปมักแสดงชื่อ + อักษรแรกของนามสกุล)"""
    n = _norm(s)
    for t in TITLES:
        if n.startswith(t) and len(n) > len(t) + 1:
            return n[len(t):]
    return n


def _name_matches(slip_name: str, real_name: str) -> bool:
    a, b = _name_key(slip_name), _name_key(real_name)
    if len(a) < 3 or len(b) < 3:
        return False
    return b.startswith(a) or a.startswith(b)


def _digits_match(masked: str, real: str) -> bool:
    """เลขที่ถูกปิดบางส่วน (xxx-x-x8459-x / xxx-xxx-6499) ตรงกับเลขจริงไหม — เทียบตามตำแหน่ง"""
    shown = re.sub(r"[^0-9xX*]", "", masked).lower().replace("*", "x")
    if len(shown) != len(real) or not re.search(r"\d{3}", shown.replace("x", " ").replace(" ", "")):
        return False
    return all(c == "x" or c == r for c, r in zip(shown, real))


def _receiver_ok(data: SlipData) -> bool | None:
    """True = ตรง, False = ไม่ตรง, None = ตั้งค่าบัญชีรับเงินไม่ครบ (ตรวจเองไม่ได้)"""
    from apps.core.services import settings_service

    pp_id = re.sub(r"\D", "", settings_service.get("PROMPTPAY_ID"))
    bank_no = re.sub(r"\D", "", settings_service.get("PROMPTPAY_BANK_ACCOUNT"))
    real_name = settings_service.get("PROMPTPAY_ACCOUNT_NAME")
    if not (pp_id or bank_no or _norm(real_name)):
        return None
    if real_name and any(_name_matches(n, real_name) for n in data.receiver_names):
        return True
    # พร้อมเพย์เบอร์โทรอาจแสดงเป็น 0066xxxxxx… ให้ลองทั้งสองรูปแบบ
    real_ids = [x for x in (pp_id, bank_no, ("66" + pp_id[1:]) if pp_id.startswith("0") else "") if x]
    for masked in data.receiver_masked_ids:
        digits_only = re.sub(r"\D", "", masked)
        if any(_digits_match(masked, rid) for rid in real_ids):
            return True
        if digits_only and digits_only in real_ids:
            return True
    return False


def _finish(slip_id, status, reason="", **fields):
    PaymentSlip.objects.filter(pk=slip_id).update(
        status=status, reason=reason[:255], verified_at=timezone.now(), **fields
    )


def _reject_order(order) -> None:
    Order.objects.filter(pk=order.pk).update(status=Order.Status.REJECTED)
    reason = PaymentSlip.objects.filter(order=order).values_list("reason", flat=True).first() or ""
    from apps.notifications.tasks import notify_admins

    notify_admins.delay(f"❌ [สลิปไม่ผ่าน] ออเดอร์ #{order.pk} ({order.user.full_name}) — {reason}")


def mark_manual_review(slip_id: int, reason: str) -> None:
    _finish(slip_id, PaymentSlip.Status.MANUAL_REVIEW, reason)
    slip = PaymentSlip.objects.select_related("order__user").get(pk=slip_id)
    from apps.notifications.tasks import notify_admins

    notify_admins.delay(
        f"⚠️ [สลิปรอตรวจ] ออเดอร์ #{slip.order_id} ({slip.order.user.full_name}) {slip.order.amount:,.0f} บาท — {reason}\n🔗 {settings.SITE_URL}/dashboard/slips/"
    )


def _notify_review(slip_id: int, reason: str) -> None:
    slip = PaymentSlip.objects.select_related("order__user").get(pk=slip_id)
    from apps.notifications.tasks import notify_admins

    notify_admins.delay(
        f"⚠️ [สลิปรอตรวจ] ออเดอร์ #{slip.order_id} ({slip.order.user.full_name}) {slip.order.amount:,.0f} บาท — {reason}\n🔗 {settings.SITE_URL}/dashboard/slips/"
    )


def verify_slip(slip_id: int) -> str:
    """คืนสถานะสุดท้ายของสลิป"""
    slip = PaymentSlip.objects.select_related("order__user").get(pk=slip_id)
    if slip.status != PaymentSlip.Status.PENDING:
        return slip.status
    order = slip.order

    if not settings.EASYSLIP_API_KEY:
        mark_manual_review(slip_id, "ยังไม่ได้ตั้งค่า EasySlip")
        return PaymentSlip.Status.MANUAL_REVIEW

    with slip.image.open("rb") as fh:
        try:
            data = verify_slip_image(fh, expected_amount=order.amount, remark=f"order-{order.pk}")
        except SlipNotFound as exc:
            _finish(slip_id, PaymentSlip.Status.REJECTED, "อ่านสลิปไม่ได้หรือไม่พบข้อมูล กรุณาอัปโหลดสลิปที่ชัดเจน")
            _reject_order(order)
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
    if data.is_duplicate and not PaymentSlip.objects.filter(trans_ref=data.trans_ref).exists():
        # EasySlip เคยเห็นสลิปนี้ แต่ระบบเราไม่มีบันทึก (เช่น ตรวจซ้ำหลังระบบขัดข้อง หรือเคยใช้ที่อื่น) → ให้คนดู
        problems.append("EasySlip แจ้งว่าสลิปนี้เคยถูกตรวจมาก่อน")
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
            _reject_order(order)
            return PaymentSlip.Status.REJECTED
        _notify_review(slip_id, reason)
        return PaymentSlip.Status.MANUAL_REVIEW

    # ยอดตรง + เลขอ้างอิงไม่ซ้ำ (+ผู้รับตรงถ้าตั้งค่าบัญชีร้านไว้) → อนุมัติและเปิดสิทธิ์ทันที เหมือน ryu_new
    try:
        with transaction.atomic():
            _finish(slip_id, PaymentSlip.Status.VERIFIED, "", trans_ref=data.trans_ref, **raw)
    except IntegrityError:  # trans_ref ซ้ำ = สลิปเคยถูกใช้แล้ว
        _finish(slip_id, PaymentSlip.Status.REJECTED, "สลิปนี้ถูกใช้งานแล้ว", **raw)
        _reject_order(order)
        return PaymentSlip.Status.REJECTED

    order_service.mark_paid(order_id=order.pk)
    from apps.core.services import audit_service

    audit_service.log(
        action="approve", model="Order", object_id=order.pk, label=f"ออเดอร์ #{order.pk}",
        actor_label="ระบบ (EasySlip)", changes={"amount": str(data.amount), "trans_ref": data.trans_ref},
    )
    return PaymentSlip.Status.VERIFIED

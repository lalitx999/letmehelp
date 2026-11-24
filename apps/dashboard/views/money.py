"""หลังบ้าน: การชำระเงิน (ออเดอร์ + สลิปรวมหน้าเดียว แบบคิวงาน)"""
import json

from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date

from apps.core.decorators import staff_required
from apps.dashboard.crud import is_fetch, json_action, modal_form
from apps.dashboard.selectors.list_params import paginate
from apps.payments.forms import ManualOrderForm, RefundForm
from apps.payments.models import Order, PaymentSlip
from apps.payments.selectors import payment_selector as sel
from apps.payments.services import order_service


# ---------- ออเดอร์ ----------
def _date_from(qs, v):
    d = parse_date(v)
    return qs.filter(created_at__date__gte=d) if d else qs


def _date_to(qs, v):
    d = parse_date(v)
    return qs.filter(created_at__date__lte=d) if d else qs


@staff_required
def order_list(request):
    """หน้า "การชำระเงิน": แท็บตามงาน (รอตรวจสลิปขึ้นก่อน) อนุมัติ/ปฏิเสธในแถวได้ กดดูรายละเอียดเปิดแผงด้านข้าง"""
    counts = sel.payment_tab_counts()
    tab = request.GET.get("tab") or ("review" if counts["review"] else "all")
    if tab not in counts:
        tab = "all"
    ls = paginate(
        request, sel.payments_qs(tab), search=("user__full_name", "user__email", "user__phone", "course__title"),
        filters={"source": "source", "from": _date_from, "to": _date_to},
        sorts={"created": ("created_at",), "amount": ("amount",), "student": ("user__full_name",)},
        default_sort="-created", per_page=25,
    )
    return render(request, "dashboard/order_list.html", {
        "ls": ls, "tab": tab,
        "tabs": [(k, label, counts[k]) for k, label, _ in sel.PAYMENT_TABS],
        "filters_ui": [("source", "ที่มา", Order.Source.choices)],
    })


@staff_required
def order_detail(request, order_id):
    order = sel.get_order_detail(order_id)
    if order is None:
        raise Http404
    ctx = {"o": order, "slips": list(order.slips.all())}
    if is_fetch(request):  # เปิดเป็นแผงด้านข้างจากหน้ารายการ
        return render(request, "dashboard/_payment_panel.html", ctx)
    return render(request, "dashboard/order_detail.html", ctx)


@staff_required
def order_form(request):
    form = ManualOrderForm(request.POST or None, initial={"email": request.GET.get("email", "")})

    def save(f):
        d = f.cleaned_data
        order_service.create_manual_order(user=f.user, course=d["course"], amount=d["amount"], days=d["days"], note=d["note"], paid=d["paid"], request=request)

    return modal_form(request, form, save=save, title="สร้างออเดอร์ให้นักเรียน", submit="สร้างออเดอร์", ok_message="สร้างออเดอร์แล้ว",
                      intro="ใช้เมื่อนักเรียนจ่ายเงินนอกระบบ (โอนเข้าบัญชีอื่น/เงินสด) ติ๊ก ชำระเงินแล้ว เพื่อเปิดสิทธิ์เรียนทันที",
                      back=reverse("dashboard:order_list"))


@json_action
def order_mark_paid(request, order_id):
    return order_service.mark_paid_manually(get_object_or_404(Order, pk=order_id), request)


@json_action
def order_cancel(request, order_id):
    return order_service.cancel_order(get_object_or_404(Order, pk=order_id), request)


@json_action
def order_resend(request, order_id):
    return order_service.resend_confirmation(get_object_or_404(Order, pk=order_id), request)


@staff_required
def order_refund(request, order_id):
    order = get_object_or_404(Order.objects.select_related("user", "course"), pk=order_id)
    form = RefundForm(request.POST or None)
    return modal_form(request, form, save=lambda f: order_service.refund_order(order, request, revoke_access=f.cleaned_data["revoke_access"], note=f.cleaned_data["note"]),
                      title="คืนเงินออเดอร์", submit="บันทึกการคืนเงิน", submit_class="btn-outline-danger", ok_message="บันทึกการคืนเงินแล้ว",
                      intro=f"ออเดอร์ #{order.pk} · {order.user.full_name} · ฿{order.amount:,.0f} — ระบบแค่บันทึกสถานะ การโอนเงินคืนต้องทำนอกระบบ",
                      back=reverse("dashboard:order_detail", args=[order.pk]))


# ---------- สลิป ----------
@staff_required
def slip_list(request):
    """ลิงก์เดิม (เมนู/อีเมลแจ้งแอดมิน) → หน้าการชำระเงิน แท็บรอตรวจ"""
    return redirect(reverse("dashboard:order_list") + "?tab=review")


@staff_required
def slip_view(request, slip_id):
    """ตัวดูสลิปใน modal: รูป + ข้อมูลที่ระบบอ่านได้"""
    slip = get_object_or_404(PaymentSlip.objects.select_related("order__user", "order__course"), pk=slip_id)
    return render(request, "dashboard/_slip_view.html", {"slip": slip})


@json_action
def slip_decide(request, slip_id):
    """แอดมินอนุมัติ/ปฏิเสธสลิปที่ระบบตรวจไม่ได้"""
    body = json.loads(request.body or "{}")
    if body.get("action") == "approve":
        order_service.approve_slip_manually(slip_id=slip_id, admin=request.user, request=request)
        return "อนุมัติแล้ว เปิดสิทธิ์เรียนให้นักเรียนแล้ว"
    if body.get("action") == "reject":
        order_service.reject_slip_manually(slip_id=slip_id, admin=request.user, reason=str(body.get("reason", ""))[:200], request=request)
        return "ปฏิเสธสลิปแล้ว"
    from apps.core.exceptions import ActionError

    raise ActionError("คำสั่งไม่ถูกต้อง")

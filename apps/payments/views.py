from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.core.decorators import staff_required
from apps.core.services import settings_service
from apps.courses.models import Course
from apps.courses.services.pricing_service import packages_for, pick_package
from apps.enrollments.selectors.enrollment_selector import get_active_enrollment

from .forms import SlipUploadForm
from .models import Order, PaymentSlip
from .selectors import payment_selector
from .services import order_service, promptpay


@login_required
def checkout(request, slug):
    course = get_object_or_404(
        Course.objects.prefetch_related("packages").only("id", "title", "slug", "price", "promo_price", "promo_ends_on", "access_days"),
        slug=slug, is_published=True,
    )
    enrollment = get_active_enrollment(request.user, course.pk)
    package = pick_package(course, request.GET.get("days"))
    order = order_service.get_or_create_pending_order(user=request.user, course=course, package=package)
    pp_id = settings_service.get("PROMPTPAY_ID")
    try:
        qr = promptpay.qr_svg(pp_id, order.amount) if pp_id else ""
    except ValueError:  # ตั้งเลขพร้อมเพย์ผิดรูปแบบในหลังบ้าน → แสดง "ยังไม่ได้ตั้งค่าบัญชี" แทน 500
        qr = ""
    return render(
        request,
        "payments/checkout.html",
        {
            "course": course,
            "order": order,
            "qr_svg": qr,
            "already_active": enrollment,
            "packages": packages_for(course),
            "selected_days": package.days,
            "account_name": settings_service.get("PROMPTPAY_ACCOUNT_NAME"),
            "promptpay_id": pp_id,
        },
    )


@login_required
@require_POST
def upload_slip(request, order_id):
    """รับสลิปแบบ Ajax → ส่งตรวจเบื้องหลัง → ให้หน้าเว็บ poll สถานะ"""
    order = payment_selector.get_user_order(request.user, order_id)
    if order is None:
        raise Http404
    if order.status in (Order.Status.PAID, Order.Status.REVIEWING):
        return JsonResponse({"ok": False, "error": "ออเดอร์นี้อยู่ระหว่างตรวจสอบหรือชำระแล้ว"}, status=409)
    form = SlipUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({"ok": False, "error": form.errors["image"][0]}, status=400)
    order_service.submit_slip(order=order, image=form.cleaned_data["image"])
    return JsonResponse({"ok": True})


@login_required
@require_GET
def order_status(request, order_id):
    order = payment_selector.get_user_order(request.user, order_id)
    if order is None:
        raise Http404
    slip = payment_selector.latest_slip_status(order) or {}
    return JsonResponse(
        {
            "order_status": order.status,
            "slip_status": slip.get("status", ""),
            "reason": slip.get("reason", ""),
            "learn_url": reverse("learning:my_courses") if order.status == Order.Status.PAID else "",
        }
    )


@staff_required
def slip_image(request, slip_id):
    """สลิปเป็นไฟล์ส่วนตัว: เปิดดูได้เฉพาะ staff"""
    slip = get_object_or_404(PaymentSlip.objects.only("id", "image"), pk=slip_id)
    return FileResponse(slip.image.open("rb"))

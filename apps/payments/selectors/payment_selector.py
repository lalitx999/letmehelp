from datetime import timedelta

from django.db.models import Count, DecimalField, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from apps.payments.models import Order, PaymentSlip


def get_user_order(user, order_id):
    return Order.objects.select_related("course").filter(pk=order_id, user=user).first()


def latest_slip_status(order):
    return PaymentSlip.objects.filter(order=order).values("status", "reason").first()


def slips_for_review(status=None):
    qs = PaymentSlip.objects.select_related("order__user", "order__course").only(
        "id", "status", "reason", "created_at", "verified_amount", "trans_ref",
        "order__id", "order__amount", "order__status", "order__is_renewal",
        "order__user__full_name", "order__user__email", "order__user__phone",
        "order__course__title",
    )
    if status:
        qs = qs.filter(status=status)
    return qs


def sales_summary(date_from=None, date_to=None):
    qs = Order.objects.filter(status=Order.Status.PAID)
    if date_from:
        qs = qs.filter(paid_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(paid_at__date__lte=date_to)
    return qs.aggregate(
        revenue=Coalesce(Sum("amount"), 0, output_field=DecimalField()), orders=Count("id")
    )


def daily_sales(days=30):
    since = timezone.localdate() - timedelta(days=days - 1)
    return list(
        Order.objects.filter(status=Order.Status.PAID, paid_at__date__gte=since)
        .annotate(day=TruncDate("paid_at"))
        .values("day")
        .annotate(revenue=Sum("amount"), orders=Count("id"))
        .order_by("day")
    )


def sales_by_course(date_from=None, date_to=None):
    qs = Order.objects.filter(status=Order.Status.PAID)
    if date_from:
        qs = qs.filter(paid_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(paid_at__date__lte=date_to)
    return list(
        qs.values("course__title").annotate(revenue=Sum("amount"), orders=Count("id")).order_by("-revenue")
    )


def paid_orders_for_export(date_from=None, date_to=None):
    qs = (
        Order.objects.filter(status=Order.Status.PAID)
        .select_related("user", "course")
        .values_list(
            "id", "paid_at", "user__full_name", "user__email", "user__phone", "course__title", "amount", "is_renewal"
        )
        .order_by("-paid_at")
    )
    if date_from:
        qs = qs.filter(paid_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(paid_at__date__lte=date_to)
    return qs


def orders_qs():
    return Order.objects.select_related("user", "course").only(
        "id", "status", "source", "amount", "duration_days", "package_label", "is_renewal", "created_at", "paid_at", "note",
        "user__id", "user__full_name", "user__email", "user__phone", "course__id", "course__title",
    )


def order_status_counts():
    return dict(Order.objects.values_list("status").annotate(n=Count("id")))


def get_order_detail(order_id):
    order = (
        Order.objects.select_related("user", "course", "created_by").prefetch_related("slips__reviewed_by").filter(pk=order_id).first()
    )
    return order

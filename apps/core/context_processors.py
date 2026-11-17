from django.conf import settings

from apps.core.services import settings_service


def site(request):
    get = settings_service.get
    return {
        "SITE_NAME": settings.SITE_NAME,
        "SITE_URL": settings.SITE_URL,
        "LINE_CONTACT_URL": get("LINE_CONTACT_URL"),
        "ANNOUNCEMENT": get("ANNOUNCEMENT"),
        "OWNER_NAME": get("OWNER_NAME") or settings.SITE_NAME,
        "CONTACT_EMAIL": get("CONTACT_EMAIL"),
        "SOCIAL_LINKS": settings_service.social_links(),
    }


def admin(request):
    """ป้ายจำนวนสลิปรอตรวจในเมนูหลังบ้าน — query เฉพาะหน้า /dashboard/ ของแอดมิน"""
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated and user.is_staff and request.path.startswith("/dashboard/")):
        return {}
    from apps.payments.models import PaymentSlip

    return {"ADMIN_PENDING_SLIPS": PaymentSlip.objects.filter(status=PaymentSlip.Status.MANUAL_REVIEW).count()}

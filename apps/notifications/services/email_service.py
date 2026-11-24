from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse


def send_expiry_reminder(*, email: str, name: str, course_title: str, course_slug: str, expires_at, days_left: int):
    renew_url = settings.SITE_URL + reverse("payments:checkout", kwargs={"slug": course_slug})
    send_mail(
        subject=f"คอร์ส {course_title} จะหมดอายุใน {days_left} วัน",
        message=(
            f"สวัสดีค่ะ/ครับ คุณ{name}\n\n"
            f"คอร์ส \"{course_title}\" จะหมดอายุวันที่ {expires_at:%d/%m/%Y}\n"
            f"ต่ออายุได้ที่: {renew_url}\n\n"
            f"{settings.SITE_NAME} — มานี่เดี๋ยวพี่สอน"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
    )


def send_payment_success(*, email: str, name: str, course_title: str, expires_at):
    send_mail(
        subject=f"ชำระเงินสำเร็จ — {course_title}",
        message=(
            f"สวัสดีค่ะ/ครับ คุณ{name}\n\n"
            f"ระบบยืนยันการชำระเงินคอร์ส \"{course_title}\" แล้ว\n"
            f"เรียนได้ถึงวันที่ {expires_at:%d/%m/%Y}\n"
            f"เข้าเรียนที่: {settings.SITE_URL}{reverse('learning:my_courses')}"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
    )


def set_password_link(user) -> str:
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    return settings.SITE_URL + reverse("accounts:password_reset_confirm", kwargs={"uidb64": uid, "token": default_token_generator.make_token(user)})


def send_set_password(user):
    """นักเรียนที่แอดมินนำเข้า: ลิงก์ตั้งรหัสผ่านครั้งแรก (ใช้ได้ครั้งเดียว อายุตาม PASSWORD_RESET_TIMEOUT)"""
    send_mail(
        subject=f"ตั้งรหัสผ่านเพื่อเข้าเรียน {settings.SITE_NAME}",
        message=(
            f"สวัสดีค่ะ คุณ{user.full_name}\n\n"
            f"เราสร้างบัญชีเรียนให้คุณที่ {settings.SITE_NAME} แล้ว (อีเมล {user.email})\n"
            f"กดลิงก์นี้เพื่อตั้งรหัสผ่านและเริ่มเรียน:\n{set_password_link(user)}\n\n"
            f"ลิงก์ใช้ได้ครั้งเดียว ถ้าหมดอายุ ขอลิงก์ใหม่ได้ที่ {settings.SITE_URL}{reverse('accounts:password_reset')}\n\n"
            f"{settings.SITE_NAME} — มานี่เดี๋ยวพี่สอน"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )

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

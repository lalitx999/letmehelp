import requests
from celery import shared_task

from .services import slip_verification_service


@shared_task(bind=True, max_retries=3)
def verify_slip_task(self, slip_id: int):
    """ตรวจสลิปเบื้องหลัง — ถ้า EasySlip ล่ม retry แบบ backoff แล้วค่อยส่งให้แอดมินตรวจมือ"""
    try:
        return slip_verification_service.verify_slip(slip_id)
    except requests.RequestException as exc:
        if self.request.retries >= self.max_retries:
            slip_verification_service.mark_manual_review(slip_id, "ระบบตรวจสลิปขัดข้อง")
            return "manual_review"
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))

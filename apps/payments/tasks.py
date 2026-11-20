import logging

import requests
from celery import shared_task

from .services import slip_verification_service
from .services.easyslip_client import EasySlipError

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def verify_slip_task(self, slip_id: int):
    """ตรวจสลิปเบื้องหลัง — ถ้า EasySlip ล่ม retry แบบ backoff แล้วค่อยส่งให้แอดมินตรวจมือ"""
    if self.request.retries == 0:
        # ส่งรูปสลิปเข้า Telegram ก่อนตรวจ เพื่อให้แอดมินเห็น "สลิปใหม่" ก่อนข้อความผลตรวจเสมอ
        from apps.notifications.tasks import notify_slip_submitted

        try:
            notify_slip_submitted(slip_id)
        except Exception:  # Telegram มีปัญหาต้องไม่ขวางการตรวจสลิป → ส่งซ้ำแยกเป็นงานเบื้องหลัง
            logger.warning("slip %s: Telegram notify failed, queued retry", slip_id, exc_info=True)
            notify_slip_submitted.delay(slip_id)
    try:
        return slip_verification_service.verify_slip(slip_id)
    except requests.RequestException as exc:
        if self.request.retries >= self.max_retries:
            reason = "ระบบตรวจสลิปขัดข้อง"
            if isinstance(exc, EasySlipError):  # เช่น QUOTA_EXCEEDED, INVALID_API_KEY, SLIP_PENDING
                reason += f" ({str(exc).split(':')[0]})"
            slip_verification_service.mark_manual_review(slip_id, reason)
            return "manual_review"
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))

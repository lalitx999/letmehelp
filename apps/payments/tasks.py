import logging

import requests
from celery import shared_task

from .services import slip_verification_service
from .services.easyslip_client import EasySlipError

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def verify_slip_task(self, slip_id: int):
    """ตรวจสลิปเบื้องหลัง — ถ้า EasySlip ล่ม retry แบบ backoff แล้วค่อยส่งให้แอดมินตรวจมือ"""
    # ตรวจก่อนให้นักเรียนรู้ผลเร็วที่สุด แล้วค่อยส่งรูปสลิป + ผลตรวจเข้า Telegram เป็นข้อความเดียว (งานแยก)
    try:
        status = slip_verification_service.verify_slip(slip_id)
    except requests.RequestException as exc:
        if self.request.retries >= self.max_retries:
            reason = "ระบบตรวจสลิปขัดข้อง"
            if isinstance(exc, EasySlipError):  # เช่น QUOTA_EXCEEDED, INVALID_API_KEY, SLIP_PENDING
                reason += f" ({str(exc).split(':')[0]})"
            slip_verification_service.mark_manual_review(slip_id, reason)
            _notify(slip_id)
            return "manual_review"
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
    _notify(slip_id)
    return status


def _notify(slip_id: int) -> None:
    from apps.notifications.tasks import notify_slip_submitted

    try:
        notify_slip_submitted.delay(slip_id)
    except Exception:  # broker มีปัญหาต้องไม่ทำให้ผลตรวจสลิปพัง
        logger.warning("slip %s: cannot queue Telegram notify", slip_id, exc_info=True)

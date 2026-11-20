"""Client สำหรับ EasySlip API V2 (เรียกแบบ sync ด้วย requests — ใช้ภายใน Celery task เท่านั้น)

เอกสาร: https://document.easyslip.com/en/v2/verify/bank/image
POST https://api.easyslip.com/v2/verify/bank  (multipart: image, checkDuplicate, matchAmount, remark)
สำเร็จ: {"success": true, "data": {"isDuplicate", "amountInSlip", "rawSlip": {...}}}
ผิดพลาด: {"success": false, "error": {"code": "SLIP_NOT_FOUND", "message": "..."}}
"""
import io
from dataclasses import dataclass, field
from decimal import Decimal

import requests
from django.conf import settings

# อ่านสลิปไม่ได้/ไม่ใช่สลิป → แจ้งนักเรียนให้อัปโหลดใหม่ (ลองซ้ำก็ไม่หาย)
SLIP_UNREADABLE = {
    "SLIP_NOT_FOUND", "VALIDATION_ERROR", "INVALID_IMAGE_FORMAT", "INVALID_IMAGE_TYPE", "IMAGE_SIZE_TOO_LARGE",
}
# ลองใหม่ภายหลังได้ (สลิปกรุงเทพที่เพิ่งโอนไม่ถึง 5 นาที / โดนจำกัดความถี่ / ฝั่ง EasySlip ขัดข้อง)
RETRYABLE = {"SLIP_PENDING", "RATE_LIMIT_EXCEEDED", "API_SERVER_ERROR", "INTERNAL_SERVER_ERROR"}


@dataclass
class SlipData:
    trans_ref: str
    amount: Decimal
    receiver_names: list[str]  # ชื่อผู้รับ (ไทย/อังกฤษ) เช่น "น.ส. ศิตา ว", "MISS SITA W"
    receiver_masked_ids: list[str]  # เลขบัญชี/พร้อมเพย์ที่ถูกปิดบางส่วน เช่น xxx-x-x8459-x, xxx-xxx-6499
    raw: dict
    is_duplicate: bool = False  # EasySlip เคยตรวจสลิปใบนี้แล้ว (จากบัญชี EasySlip เดียวกัน)
    sender_name: str = ""
    sender_bank: str = ""
    extra: dict = field(default_factory=dict)


class SlipNotFound(Exception):
    """EasySlip อ่านสลิปไม่ได้ หรือไม่พบข้อมูลสลิป"""


class EasySlipError(requests.RequestException):
    """ใช้งานไม่ได้ชั่วคราว/ตั้งค่าผิด (คีย์ผิด, โควตาหมด, ระบบล่ม) → Celery ลองซ้ำ แล้วส่งให้แอดมินตรวจมือ
    สืบทอด RequestException เพื่อให้ verify_slip_task จัดการเหมือนเน็ตหลุด"""


def _err(resp) -> tuple[str, str]:
    try:
        e = resp.json().get("error") or {}
    except ValueError:
        return f"HTTP_{resp.status_code}", ""
    return str(e.get("code") or f"HTTP_{resp.status_code}"), str(e.get("message") or "")


def _names(account: dict) -> list[str]:
    name = account.get("name") or {}
    if isinstance(name, dict):
        return [v for v in name.values() if isinstance(v, str) and v.strip()]
    return [name] if isinstance(name, str) and name.strip() else []


MAX_IMAGE_BYTES = 4 * 1024 * 1024  # EasySlip V2 รับรูปไม่เกิน 4MB (เว็บเรารับอัปโหลดถึง 8MB)


def _fit_image(file_obj) -> bytes:
    """คืน bytes ของรูปที่ไม่เกิน 4MB — ถ้าใหญ่เกินจะย่อ/บีบเป็น JPEG (QR ในสลิปยังอ่านได้)"""
    data = file_obj.read() if hasattr(file_obj, "read") else bytes(file_obj)
    if len(data) <= MAX_IMAGE_BYTES:
        return data
    from PIL import Image

    img = Image.open(io.BytesIO(data))
    img = img.convert("RGB")
    for side, quality in ((2400, 88), (2000, 85), (1600, 80), (1280, 75)):
        img.thumbnail((side, side))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=quality, optimize=True)
        if out.tell() <= MAX_IMAGE_BYTES:
            return out.getvalue()
    return out.getvalue()


def verify_slip_image(file_obj, *, expected_amount: Decimal | None = None, remark: str = "") -> SlipData:
    form = {"checkDuplicate": "true"}
    if expected_amount is not None:
        form["matchAmount"] = f"{Decimal(expected_amount):.2f}"
    if remark:
        form["remark"] = remark[:255]
    resp = requests.post(
        settings.EASYSLIP_API_URL,
        headers={"Authorization": f"Bearer {settings.EASYSLIP_API_KEY}"},
        files={"image": ("slip.jpg", _fit_image(file_obj))},
        data=form,
        timeout=20,
    )
    if resp.status_code != 200:
        code, message = _err(resp)
        if code in SLIP_UNREADABLE:
            raise SlipNotFound(f"{code}: {message}")
        # 401/403 (คีย์ผิด, โควตาหมด, IP ไม่อยู่ใน whitelist), 429, 5xx, SLIP_PENDING
        raise EasySlipError(f"{code}: {message}"[:200])

    payload = resp.json()
    d = payload.get("data") or {}
    slip = d.get("rawSlip") or {}
    if not payload.get("success") or not slip:
        raise SlipNotFound("no_slip_data")

    receiver = slip.get("receiver") or {}
    r_acct = receiver.get("account") or {}
    masked = [
        str(v) for v in (
            (r_acct.get("bank") or {}).get("account"),
            (r_acct.get("proxy") or {}).get("account"),
        ) if v
    ]
    matched = d.get("matchedAccount") or {}
    if matched.get("bankNumber"):
        masked.append(str(matched["bankNumber"]))

    amount = d.get("amountInSlip")
    if amount is None:
        amt = slip.get("amount")
        amount = amt.get("amount") if isinstance(amt, dict) else amt

    sender = slip.get("sender") or {}
    s_names = _names(sender.get("account") or {})
    return SlipData(
        trans_ref=str(slip.get("transRef") or ""),
        amount=Decimal(str(amount or 0)),
        receiver_names=_names(r_acct) + [n for n in (matched.get("nameTh"), matched.get("nameEn")) if n],
        receiver_masked_ids=masked,
        raw=payload,
        is_duplicate=bool(d.get("isDuplicate")),
        sender_name=s_names[0] if s_names else "",
        sender_bank=str((sender.get("bank") or {}).get("short") or ""),
        extra={"date": slip.get("date")},
    )

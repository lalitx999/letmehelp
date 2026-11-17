"""Client สำหรับ EasySlip (เรียกแบบ sync ด้วย requests — ใช้ภายใน Celery task เท่านั้น)"""
from dataclasses import dataclass
from decimal import Decimal

import requests
from django.conf import settings


@dataclass
class SlipData:
    trans_ref: str
    amount: Decimal
    receiver_names: list[str]  # ชื่อผู้รับ (ไทย/อังกฤษ)
    receiver_masked_ids: list[str]  # เลขบัญชี/พร็อกซีที่ถูกปิดบางส่วน เช่น xxx-xxx-5678
    raw: dict


class SlipNotFound(Exception):
    """EasySlip อ่านสลิปไม่ได้ หรือไม่พบข้อมูลสลิป"""


def verify_slip_image(file_obj) -> SlipData:
    resp = requests.post(
        settings.EASYSLIP_API_URL,
        headers={"Authorization": f"Bearer {settings.EASYSLIP_API_KEY}"},
        files={"file": file_obj},
        timeout=20,
    )
    if resp.status_code >= 500 or resp.status_code in (401, 403, 429):
        resp.raise_for_status()  # ให้ Celery retry / ส่งเข้าตรวจมือ
    payload = resp.json()
    if resp.status_code != 200 or payload.get("status") != 200 or "data" not in payload:
        raise SlipNotFound(payload.get("message", "slip_not_found"))

    d = payload["data"]
    receiver = d.get("receiver") or {}
    acct = receiver.get("account") or {}
    proxy = receiver.get("proxy") or {}
    names = [n for n in (acct.get("name") or {}).values() if isinstance(n, str)] if isinstance(acct.get("name"), dict) else []
    # รูปแบบ response ต่างกันตามเวอร์ชัน: ลองทุกตำแหน่งที่เป็นไปได้ของเลขบัญชี/พร็อกซี (ที่ถูกปิดบางส่วน เช่น xxx-xxx-1234)
    candidates = [
        acct.get("value"), proxy.get("value"), proxy.get("account"),
        (acct.get("proxy") or {}).get("account"), (acct.get("bank") or {}).get("account"), acct.get("account"),
    ]
    masked = [str(v) for v in candidates if v and isinstance(v, (str, int))]
    amount_raw = d.get("amount")
    amount = amount_raw.get("amount") if isinstance(amount_raw, dict) else amount_raw
    return SlipData(
        trans_ref=d.get("transRef") or d.get("payload") or "",
        amount=Decimal(str(amount or 0)),
        receiver_names=names,
        receiver_masked_ids=masked,
        raw=payload,
    )

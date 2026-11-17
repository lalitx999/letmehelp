"""สร้าง PromptPay QR (EMVCo / Thai QR Payment) ตามยอดเงินของออเดอร์"""
import io
from decimal import Decimal

import qrcode
from qrcode.image.svg import SvgPathImage


def _tlv(tag: str, value: str) -> str:
    return f"{tag}{len(value):02d}{value}"


def _crc16(data: str) -> str:
    crc = 0xFFFF
    for byte in data.encode("ascii"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def build_payload(promptpay_id: str, amount: Decimal | None = None) -> str:
    target = "".join(ch for ch in promptpay_id if ch.isdigit())
    if len(target) >= 13:  # เลขบัตรประชาชน / Tax ID
        proxy = _tlv("02", target)
    else:  # เบอร์โทร → 0066XXXXXXXXX
        proxy = _tlv("01", "0066" + target.lstrip("0"))
    merchant = _tlv("29", _tlv("00", "A000000677010111") + proxy)
    parts = [
        _tlv("00", "01"),
        _tlv("01", "12" if amount else "11"),
        merchant,
        _tlv("53", "764"),
    ]
    if amount:
        parts.append(_tlv("54", f"{Decimal(amount):.2f}"))
    parts += [_tlv("58", "TH")]
    body = "".join(parts) + "6304"
    return body + _crc16(body)


def qr_svg(promptpay_id: str, amount: Decimal) -> str:
    """คืนค่า SVG (string) สำหรับฝังในหน้าเว็บ"""
    img = qrcode.make(build_payload(promptpay_id, amount), image_factory=SvgPathImage, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    svg = buf.getvalue().decode()
    return svg[svg.index("<svg"):]

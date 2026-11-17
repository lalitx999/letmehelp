"""แพ็กเกจราคาของคอร์ส: แพ็กเกจหลัก (Course.price/access_days) + แพ็กเกจเสริม (CoursePackage)"""
from dataclasses import dataclass
from decimal import Decimal

from apps.courses.models import CoursePackage


@dataclass(frozen=True)
class Package:
    days: int
    label: str
    price: Decimal
    list_price: Decimal | None = None  # ราคาปกติ (มีค่าเมื่ออยู่ในช่วงโปรโมชัน ใช้ขีดฆ่าในหน้าเว็บ)

    @property
    def is_lifetime(self) -> bool:
        return self.days >= 3650


def duration_label(days: int) -> str:
    if days >= 3650:
        return "ตลอดชีพ"
    if days % 365 == 0:
        return f"{days // 365} ปี"
    if days % 30 == 0 and days >= 60:
        return f"{days // 30} เดือน"
    return f"{days} วัน"


def packages_for(course) -> list[Package]:
    """เรียงตามอายุ น้อย→มาก; ถ้า days ซ้ำกับแพ็กเกจหลัก ให้แพ็กเกจเสริมแทนที่"""
    list_price = course.price if course.promo_active else None
    found = {course.access_days: Package(course.access_days, duration_label(course.access_days), course.current_price, list_price)}
    for p in course.packages.all():  # ต้อง prefetch มาแล้ว หรือยอมให้ยิง 1 query
        if p.is_active:
            found[p.days] = Package(p.days, p.label or duration_label(p.days), p.price)
    return [found[d] for d in sorted(found)]


def pick_package(course, days) -> Package:
    pkgs = packages_for(course)
    try:
        wanted = int(days)
    except (TypeError, ValueError):
        return pkgs[0]
    return next((p for p in pkgs if p.days == wanted), pkgs[0])

"""แบ่งหน้า + ค้นหา + กรอง + เรียงลำดับ ให้ทุกหน้า list ในหลังบ้านใช้ร่วมกัน"""
from dataclasses import dataclass, field
from functools import reduce
from operator import or_
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db.models import Q


@dataclass
class ListState:
    page: object
    q: str = ""
    sort: str = ""
    filters: dict = field(default_factory=dict)
    querystring: str = ""  # query ปัจจุบันที่ไม่รวม page (ใช้ต่อท้ายลิงก์เรียง/กรอง)
    total: int = 0


def paginate(request, qs, *, search=(), filters=None, sorts=None, default_sort="", per_page=20) -> ListState:
    """search: ฟิลด์ที่ค้นด้วย icontains · filters: {ชื่อพารามิเตอร์: ฟิลด์ หรือ callable(qs, ค่า)} · sorts: {คีย์: ('field',...)}"""
    q = request.GET.get("q", "").strip()
    if q and search:
        qs = qs.filter(reduce(or_, (Q(**{f"{f}__icontains": q}) for f in search)))

    active = {}
    for name, target in (filters or {}).items():
        value = request.GET.get(name, "").strip()
        if not value:
            continue
        active[name] = value
        qs = target(qs, value) if callable(target) else qs.filter(**{target: value})

    sort = request.GET.get("sort") or default_sort
    if sorts and sort.lstrip("-") in sorts:
        order = sorts[sort.lstrip("-")]
        qs = qs.order_by(*(("-" + o if sort.startswith("-") else o) for o in order))
    elif sorts and default_sort in sorts:
        qs = qs.order_by(*sorts[default_sort])

    params = {k: v for k, v in request.GET.items() if k != "page" and v}
    paginator = Paginator(qs, per_page)
    page = paginator.get_page(request.GET.get("page"))
    return ListState(page=page, q=q, sort=sort, filters=active, querystring=urlencode(params), total=paginator.count)

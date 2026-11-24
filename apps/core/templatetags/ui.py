from django import template

register = template.Library()


@register.filter
def hms(seconds):
    """วินาที → ชม.:นาที / นาที:วินาที"""
    seconds = int(seconds or 0)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


@register.filter
def hours_minutes(seconds):
    seconds = int(seconds or 0)
    if seconds < 60:
        return f"{seconds} วินาที"
    h, m = divmod(seconds // 60, 60)
    return f"{h} ชม. {m} นาที" if h else f"{m} นาที"


@register.filter
def get_item(d, key):
    return d.get(key)


@register.filter
def json_str(value):
    """ค่าสตริงสำหรับฝังใน JSON-LD (escape เพื่อกัน </script> injection)"""
    import json

    from django.utils.safestring import mark_safe

    return mark_safe(json.dumps(str(value), ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


_CAT_STYLES = {
    "tgat": ("is-blue", "mortarboard"),
    "a-level": ("is-red", "trophy"),
    "grammar": ("is-orange", "spellcheck"),
    "vocab": ("is-blue", "book-half"),
    "conversation": ("is-orange", "chat-dots"),
    "reading": ("is-red", "journal-text"),
}


@register.simple_tag
def icon(name, cls=""):
    """แสดงไอคอนจาก sprite (Bootstrap Icons) — ใช้ {% icon "play-circle" "icon-lg" %}"""
    from django.templatetags.static import static
    from django.utils.html import format_html

    return format_html(
        '<svg class="icon {}" aria-hidden="true"><use href="{}#{}"/></svg>',
        cls, static("vendor/bootstrap-icons/icons.svg"), name,
    )


@register.simple_tag
def cat_style(slug):
    """คืน (class สี, ชื่อไอคอน) ของหมวด — ใช้ทำปกคอร์สเมื่อไม่มีรูป"""
    return _CAT_STYLES.get(slug, ("is-ink", "book"))


@register.filter
def initial(name):
    return (str(name or "?").strip()[:1] or "?").upper()


@register.simple_tag
def course_cover(course):
    """URL ภาพปกคอร์ส ตามลำดับ: รูปที่อัปโหลด > ลิงก์ภาพ (cover_url) > ภาพจาก YouTube ของคลิปดูฟรีแรก > ว่าง"""
    from django.templatetags.static import static

    thumb = getattr(course, "thumbnail", None)
    if thumb:
        try:
            return thumb.url
        except ValueError:
            pass
    url = (getattr(course, "cover_url", "") or "").strip()
    if url:
        return static(url[len("/static/"):]) if url.startswith("/static/") else url
    vid = getattr(course, "first_video_id", None)
    return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else ""


@register.filter
def package_days(days):
    from apps.courses.services.pricing_service import duration_label

    return duration_label(int(days or 0))


@register.simple_tag(takes_context=True)
def sort_th(context, key, label):
    """หัวคอลัมน์ที่คลิกเรียงได้ — สลับ asc/desc และคงตัวกรองเดิมไว้"""
    from urllib.parse import urlencode

    from django.utils.html import format_html

    req = context["request"]
    ls = context.get("ls")
    cur = (req.GET.get("sort") or (ls.sort if ls else "")) or ""
    params = {k: v for k, v in req.GET.items() if k not in ("sort", "page") and v}
    params["sort"] = "-" + key if cur == key else key
    arrow = ""
    if cur == key:
        arrow = icon("arrow-up-short")
    elif cur == "-" + key:
        arrow = icon("arrow-down-short")
    return format_html('<a class="sort-link" href="?{}">{}{}</a>', urlencode(params), label, arrow)

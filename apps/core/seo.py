"""SEO / AEO: ข้อมูลโครงสร้าง (schema.org JSON-LD) และข้อเท็จจริงกลางของเว็บ — ใช้ร่วมกันทั้งหน้าเว็บ, JSON-LD และ llms.txt

แก้ข้อมูลแบรนด์/ผู้สอนที่นี่ที่เดียว แล้วทุกหน้าจะตรงกัน (AI และ Google ชอบข้อมูลที่ตรงกันทุกที่)
"""
from django.conf import settings
from django.templatetags.static import static
from django.urls import reverse

BRAND = "Let Me Help"
BRAND_TH = "มานี่เดี๋ยวพี่สอน"
TAGLINE = "อังกฤษสนุก เข้าใจง่าย ประหยัดเวลา คุ้มราคา"
SUMMARY = (
    "Let Me Help (มานี่เดี๋ยวพี่สอน) คือเว็บคอร์สเรียนออนไลน์ภาษาอังกฤษสำหรับนักเรียนมัธยมที่เตรียมสอบ TGAT และ A-Level "
    "สอนโดยพี่ใยไหม ศิษย์เก่าคณะอักษรศาสตร์ จุฬาลงกรณ์มหาวิทยาลัย (รุ่น 82) เกียรตินิยมอันดับหนึ่ง เหรียญทอง "
    "มีประสบการณ์สอน 10 ปี เรียนผ่านวิดีโอได้ทุกอุปกรณ์ ดูซ้ำได้ตลอดอายุคอร์ส 1 ปี มีเอกสาร PDF และหนังสือเล่ม"
)
INSTRUCTOR = {
    "name": "พี่ใยไหม",
    "role": "ผู้สอนและผู้ก่อตั้ง Let Me Help",
    "education": "คณะอักษรศาสตร์ จุฬาลงกรณ์มหาวิทยาลัย รุ่น 82",
    "honors": "เกียรตินิยมอันดับหนึ่ง เหรียญทอง",
    "experience_years": 10,
}
# ข้อเท็จจริงของบริการ — ตรงกับระบบจริง (ราคาดึงจากฐานข้อมูลแยกต่างหาก)
FACTS = [
    ("วิชา", "ภาษาอังกฤษสำหรับสอบ TGAT (TGAT1 การสื่อสารภาษาอังกฤษ) และ A-Level ภาษาอังกฤษ"),
    ("กลุ่มผู้เรียน", "นักเรียนมัธยมปลายที่เตรียมสอบเข้ามหาวิทยาลัยระบบ TCAS"),
    ("ผู้สอน", f"{INSTRUCTOR['name']} — {INSTRUCTOR['education']}, {INSTRUCTOR['honors']}, ประสบการณ์สอน {INSTRUCTOR['experience_years']} ปี"),
    ("รูปแบบการเรียน", "คลิปวิดีโอออนไลน์ เรียนเมื่อไหร่ก็ได้ ผ่านคอมพิวเตอร์ แท็บเล็ต และสมาร์ตโฟน (ติดตั้งเป็นแอปบนมือถือได้)"),
    ("อายุคอร์ส", "1 ปี (365 วัน) นับจากวันที่ชำระเงินสำเร็จ ดูซ้ำได้ไม่จำกัดครั้งตลอดอายุคอร์ส"),
    ("เอกสารประกอบ", "ไฟล์ PDF ในบทเรียน และหนังสือเล่มจริงสั่งซื้อแยกได้"),
    ("ระบบช่วยเรียน", "จำตำแหน่งวิดีโอที่ดูค้างไว้ (ย้อนให้ 10 วินาที), สมุดโน้ตแทรกเวลาในวิดีโอ, ปฏิทินและสถิติวันเรียนต่อเนื่อง"),
    ("การชำระเงิน", "สแกน QR PromptPay แล้วอัปโหลดสลิป ระบบตรวจสลิปอัตโนมัติและเปิดสิทธิ์เรียนทันทีเมื่อยอดถูกต้อง"),
    ("ทดลองเรียน", "มีคลิปตัวอย่างให้ดูฟรีโดยไม่ต้องสมัครสมาชิก"),
]


def abs_url(path: str) -> str:
    return settings.SITE_URL.rstrip("/") + path


def _same_as():
    from apps.core.services import settings_service

    links = [s["url"] for s in settings_service.social_links()]
    line = settings_service.get("LINE_CONTACT_URL")
    return links + ([line] if line else [])


def instructor() -> dict:
    return {
        "@type": "Person",
        "@id": abs_url("/about/#instructor"),
        "name": INSTRUCTOR["name"],
        "jobTitle": INSTRUCTOR["role"],
        "description": f"{INSTRUCTOR['education']} · {INSTRUCTOR['honors']} · ประสบการณ์สอนภาษาอังกฤษ {INSTRUCTOR['experience_years']} ปี",
        "alumniOf": {"@type": "CollegeOrUniversity", "name": "จุฬาลงกรณ์มหาวิทยาลัย", "department": {"@type": "Organization", "name": "คณะอักษรศาสตร์"}},
        "award": INSTRUCTOR["honors"],
        "knowsAbout": ["ภาษาอังกฤษ", "TGAT", "A-Level ภาษาอังกฤษ", "การเตรียมสอบ TCAS"],
        "worksFor": {"@id": abs_url("/#organization")},
    }


def organization() -> dict:
    return {
        "@type": "EducationalOrganization",
        "@id": abs_url("/#organization"),
        "name": BRAND,
        "alternateName": BRAND_TH,
        "url": abs_url("/"),
        "logo": abs_url(static("img/icon-512.png")),
        "image": abs_url(static("img/logo.png")),
        "description": SUMMARY,
        "slogan": TAGLINE,
        "sameAs": _same_as(),
        "founder": {"@id": abs_url("/about/#instructor")},
        "areaServed": {"@type": "Country", "name": "ประเทศไทย"},
        "knowsLanguage": ["th", "en"],
    }


def website() -> dict:
    return {
        "@type": "WebSite",
        "@id": abs_url("/#website"),
        "name": BRAND,
        "alternateName": BRAND_TH,
        "url": abs_url("/"),
        "inLanguage": "th-TH",
        "publisher": {"@id": abs_url("/#organization")},
    }


def graph(*nodes) -> dict:
    return {"@context": "https://schema.org", "@graph": [n for n in nodes if n]}


def faq_page(faqs, url_path: str) -> dict:
    return {
        "@type": "FAQPage",
        "@id": abs_url(url_path + "#faq"),
        "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs],
    }


def breadcrumbs(items) -> dict:
    """items = [(ชื่อ, path)]"""
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [{"@type": "ListItem", "position": i, "name": name, "item": abs_url(path)} for i, (name, path) in enumerate(items, start=1)],
    }


def course(course, total_seconds: int = 0, cover: str = "") -> dict:
    """total_seconds = ความยาววิดีโอรวม → courseWorkload (เวลาเรียนทั้งหมดของคอร์สแบบเรียนเองตามสะดวก)"""
    url = abs_url(reverse("courses:detail", args=[course.slug]))
    data = {
        "@type": "Course",
        "@id": url + "#course",
        "name": course.title,
        "description": (course.subtitle or course.description or course.title)[:500],
        "url": url,
        "inLanguage": "th",
        "educationalLevel": "มัธยมศึกษาตอนปลาย",
        "teaches": f"ภาษาอังกฤษสำหรับสอบ {course.category.name}",
        "about": [course.category.name, "ภาษาอังกฤษ"],
        "provider": {"@id": abs_url("/#organization")},
        "instructor": [{"@id": abs_url("/about/#instructor")}],
        "isAccessibleForFree": False,
        "offers": [{
            "@type": "Offer",
            "category": "Paid",
            "price": f"{course.current_price:.2f}",
            "priceCurrency": "THB",
            "availability": "https://schema.org/InStock",
            "url": url,
            **({"priceValidUntil": course.promo_ends_on.isoformat()} if course.promo_active and course.promo_ends_on else {}),
        }],
        "hasCourseInstance": [{
            "@type": "CourseInstance",
            "courseMode": "Online",
            "instructor": [{"@id": abs_url("/about/#instructor")}],
            **({"courseWorkload": _iso_duration(total_seconds)} if total_seconds else {}),
        }],
    }
    if cover:
        data["image"] = cover if cover.startswith("http") else abs_url(cover)
    return data


def _iso_duration(seconds: int) -> str:
    h, m = divmod(round(seconds / 60), 60)
    return f"PT{h}H{m}M" if h else f"PT{max(m, 1)}M"


def item_list(courses) -> dict:
    return {
        "@type": "ItemList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "url": abs_url(reverse("courses:detail", args=[c.slug])), "name": c.title}
            for i, c in enumerate(courses, start=1)
        ],
    }

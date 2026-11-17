from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.cache import cache_control

from apps.courses.selectors.course_selector import featured_courses, free_preview_lessons, list_categories


# หมวดที่วางแผนเปิดในอนาคต (ยังไม่มีคอร์ส) — แสดงเป็นแผนงานบนหน้าแรก
UPCOMING_SUBJECTS = [
    ("Grammar", "ไวยากรณ์ตั้งแต่พื้นฐานถึงออกสอบ", "spellcheck"),
    ("Vocab", "คำศัพท์ที่ใช้บ่อยในข้อสอบ", "book-half"),
    ("Conversation", "สนทนาและสำนวนในชีวิตจริง", "chat-dots"),
    ("Reading", "เทคนิคอ่านจับใจความ", "journal-text"),
]

FAQS = [
    ("ซื้อคอร์สแล้วเรียนได้นานแค่ไหน", "แต่ละคอร์สกำหนดอายุการเรียนไว้ชัดเจนในหน้ารายละเอียดคอร์ส เมื่อชำระเงินและสลิปผ่านการตรวจ ระบบจะเปิดสิทธิ์ให้ทันที และดูซ้ำได้ไม่จำกัดครั้งตลอดอายุคอร์ส"),
    ("ชำระเงินอย่างไร", "สแกน QR PromptPay ตามยอดของคอร์ส แล้วอัปโหลดสลิปในหน้าชำระเงิน ระบบจะตรวจยอดและบัญชีผู้รับให้อัตโนมัติ หากตรวจอัตโนมัติไม่ได้ ผู้ดูแลจะช่วยตรวจให้"),
    ("ดูบนมือถือหรือแท็บเล็ตได้ไหม", "ได้ เว็บรองรับทั้งคอมพิวเตอร์ แท็บเล็ต และสมาร์ตโฟน และเพิ่มเป็นไอคอนบนหน้าจอมือถือให้ใช้งานเหมือนแอปได้"),
    ("ถ้าปิดวิดีโอกลางคลิป จะเรียนต่อได้ไหม", "ได้ ระบบจำตำแหน่งล่าสุดที่เรียนค้างไว้ และเมื่อกลับมาจะถอยหลังให้อัตโนมัติ 10 วินาทีเพื่อให้ต่อเรื่องได้ทัน"),
    ("คอร์สใกล้หมดอายุ ต่ออายุได้ไหม", "ได้ ระบบจะส่งอีเมลแจ้งเตือนก่อนหมดอายุ และกดต่ออายุได้จากหน้า Dashboard วันที่เหลืออยู่จะไม่หายไป"),
]


def _calendar_demo():
    """ตัวอย่างปฏิทินความเข้มข้นบนหน้าแรก (ภาพประกอบ ไม่ใช่ข้อมูลจริง)"""
    pattern = "l1 l2 - l3 l2 - l1 l3 l3 l2 - l1 l2 l3 - l2 l3 l1 - - l2 l3 l3 l2 l1 - l3 l2 l1 l2 l3".split()
    return ["" if p == "-" else p for p in pattern][:28]


# รูปประกอบของแต่ละหมวดบนหน้าแรก (Unsplash License)
SUBJECT_IMAGES = {"tgat": "img/covers/tgat.jpg", "a-level": "img/covers/a-level.jpg"}


def home(request):
    categories = list_categories()
    subjects = [{"cat": c, "image": SUBJECT_IMAGES.get(c.slug)} for c in categories]
    active = {c.name.lower() for c in categories}
    soon = [s for s in UPCOMING_SUBJECTS if s[0].lower() not in active]
    return render(
        request,
        "core/home.html",
        {
            "categories": categories,
            "subjects": subjects,
            "soon": soon,
            "featured_courses": featured_courses(limit=6),
            "faqs": FAQS,
            "cal_demo": _calendar_demo(),
        },
    )


def robots_txt(request):
    body = (
        "User-agent: *\n"
        "Disallow: /dashboard/\n"
        "Disallow: /django-admin/\n"
        "Disallow: /learn/\n"
        "Disallow: /payments/\n"
        "Disallow: /accounts/\n"
        f"Sitemap: {settings.SITE_URL}/sitemap.xml\n"
    )
    return HttpResponse(body, content_type="text/plain")


@cache_control(max_age=3600)
def manifest(request):
    """PWA manifest — ให้เพิ่มเว็บเป็นไอคอนบนหน้าจอมือถือได้"""
    data = {
        "name": "Let Me Help — มานี่เดี๋ยวพี่สอน",
        "short_name": "Let Me Help",
        "description": "คอร์สเรียนออนไลน์ภาษาอังกฤษ TGAT / A-Level",
        "id": "/",
        "start_url": "/learn/my-courses/?source=pwa",
        "scope": "/",
        "display": "standalone",
        "orientation": "any",
        "background_color": "#ffffff",
        "theme_color": "#ffffff",
        "lang": "th",
        "dir": "ltr",
        "categories": ["education"],
        # รูปมีขอบขาวเว้นรอบตัวการ์ตูนอยู่แล้ว (อยู่ใน safe zone 80%) จึงใช้ไฟล์เดียวกันเป็นทั้ง any และ maskable โดยแยกรายการ
        "icons": [
            {"src": static("img/icon-192.png"), "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": static("img/icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": static("img/icon-192.png"), "sizes": "192x192", "type": "image/png", "purpose": "maskable"},
            {"src": static("img/icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
        "shortcuts": [
            {"name": "Dashboard ของฉัน", "short_name": "Dashboard", "url": "/learn/my-courses/",
             "icons": [{"src": static("img/icon-192.png"), "sizes": "192x192", "type": "image/png"}]},
            {"name": "คอร์สทั้งหมด", "short_name": "คอร์ส", "url": "/courses/",
             "icons": [{"src": static("img/icon-192.png"), "sizes": "192x192", "type": "image/png"}]},
        ],
    }
    return JsonResponse(data, content_type="application/manifest+json")


@cache_control(max_age=0, no_cache=True)
def service_worker(request):
    """Service worker ต้องเสิร์ฟจาก root เพื่อให้ scope ครอบทั้งเว็บ"""
    return render(request, "core/sw.js", {}, content_type="application/javascript")


def offline(request):
    return render(request, "core/offline.html")


POLICY_UPDATED = "14 พฤศจิกายน 2569"  # แก้วันที่ทุกครั้งที่ปรับเนื้อหานโยบาย/ข้อกำหนด


def privacy(request):
    return render(request, "core/privacy.html", {"updated": POLICY_UPDATED})


def terms(request):
    return render(request, "core/terms.html", {"updated": POLICY_UPDATED})


def free_trial(request):
    return render(request, "core/free_trial.html", {"groups": free_preview_lessons()})


GUIDE_TIPS = [
    ("person-plus", "is-red", "1. สมัครสมาชิก", "กรอกชื่อ เบอร์โทร และอีเมล แล้วเข้าสู่ระบบด้วยอีเมลและรหัสผ่านที่ตั้งไว้"),
    ("qr-code", "is-blue", "2. ชำระเงิน", "เลือกแพ็กเกจที่ต้องการ สแกน QR PromptPay ตามยอด แล้วอัปโหลดสลิป ระบบตรวจให้อัตโนมัติ"),
    ("play-circle", "is-orange", "3. เริ่มเรียน", "เปิดสิทธิ์เมื่อสลิปผ่าน ไปที่ Dashboard แล้วกด เริ่มเรียน หรือ เรียนต่อ"),
    ("journal-text", "is-green", "4. จดโน้ตระหว่างเรียน", "ในหน้าเรียนมีสมุดโน้ตส่วนตัว กดปุ่มแทรกเวลาเพื่อบันทึกจุดสำคัญ แล้วคลิกเวลาเพื่อข้ามไปจุดนั้นได้"),
    ("calendar-check", "is-blue", "5. ติดตามความต่อเนื่อง", "ดูปฏิทินและสถิติการเรียนที่หน้า สถิติการเรียน เรียนทุกวันเพื่อสะสมจำนวนวันต่อเนื่อง"),
    ("arrow-repeat", "is-red", "6. ต่ออายุ", "ก่อนหมดอายุระบบส่งอีเมลเตือน กดต่ออายุได้ที่หน้า Dashboard วันที่เหลืออยู่จะนับต่อให้"),
]


def guide(request):
    return render(request, "core/guide.html", {"faqs": FAQS, "tips": GUIDE_TIPS})

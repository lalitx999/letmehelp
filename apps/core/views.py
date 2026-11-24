from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.cache import cache_control

from apps.courses.selectors.course_selector import free_preview_lessons, search_published_courses


FAQS = [
    ("ชำระเงินอย่างไร", "สแกน QR PromptPay ตามยอดของคอร์ส แล้วอัปโหลดสลิปในหน้าชำระเงิน ระบบจะตรวจยอดและบัญชีผู้รับให้อัตโนมัติ หากมีข้อผิดพลาดใดๆ สามารถติดต่อแอดมินผ่าน LINE: araremm ได้เลย"),
    ("ซื้อคอร์สแล้วเรียนได้นานแค่ไหน", "แต่ละคอร์สมีอายุ 1 ปี เมื่อชำระเงินและสลิปผ่านการตรวจ ระบบจะอนุมัติให้ และสามารถเรียนได้ทันที"),
    ("ดูบนอุปกรณ์ใดได้บ้าง", "เว็บไซต์รองรับทั้งคอมพิวเตอร์ แท็บเล็ต และสมาร์ตโฟน และสามารถเพิ่มเป็นไอคอนบนหน้าจอมือถือให้ใช้งานเหมือนแอปพลิเคชันได้"),
    ("ถ้าปิดวิดีโอกลางคัน ครั้งหน้าจะเรียนต่อได้ไหม", "ได้ ระบบจะจดจำตำแหน่งล่าสุดที่เรียนค้างไว้ พร้อมถอยหลังให้อัตโนมัติ 10 วินาทีเพื่อให้ปะติดปะต่อเนื้อหาเดิมได้"),
    ("คอร์สใกล้หมดอายุ ต่ออายุได้ไหม", "ได้ ระบบจะส่งอีเมลแจ้งเตือนก่อนหมดอายุ และกดต่ออายุได้จากหน้า Dashboard วันที่เหลืออยู่จะไม่หายไป"),
]

# โปสเตอร์คอร์สบนหน้าแรก (หมวด slug, ภาพ, ชื่อ) — กดแล้วไปหน้าคอร์สในหมวดนั้น
COURSE_POSTERS = [
    ("tgat", "img/home/course-tgat.jpg", "ตะลุยโจทย์ TGAT 5 พ.ศ."),
    ("a-level", "img/home/course-alevel.jpg", "ตะลุยโจทย์ A-Level 6 พ.ศ."),
]


def _course_posters():
    """ถ้าหมวดมีคอร์สเดียว ลิงก์ตรงไปหน้าคอร์ส ไม่งั้นไปหน้ารายการคอร์สของหมวด"""
    by_cat = {}
    for c in search_published_courses().filter(category__slug__in=[slug for slug, _, _ in COURSE_POSTERS]):
        by_cat.setdefault(c.category.slug, []).append(c)
    posters = []
    for slug, image, title in COURSE_POSTERS:
        courses = by_cat.get(slug, [])
        if len(courses) == 1:
            url = reverse("courses:detail", args=[courses[0].slug])
        else:
            url = reverse("courses:list") + f"?category={slug}"
        posters.append({"image": image, "title": title, "url": url})
    return posters


def home(request):
    return render(request, "core/home.html", {"posters": _course_posters(), "faqs": FAQS})


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

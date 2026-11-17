"""PWA · คุกกี้ · นโยบาย/ข้อกำหนด · Footer · การยอมรับข้อกำหนดตอนสมัคร"""
import json

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.core.models import SiteSetting


class PwaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_manifest_is_installable(self):
        m = json.loads(self.client.get(reverse("core:manifest")).content)
        self.assertEqual((m["display"], m["lang"]), ("standalone", "th"))
        purposes = {(i["sizes"], i["purpose"]) for i in m["icons"]}
        # ต้องมี 192/512 ทั้ง any และ maskable แยกรายการ (ห้ามรวมเป็น "any maskable")
        self.assertEqual(purposes, {("192x192", "any"), ("512x512", "any"), ("192x192", "maskable"), ("512x512", "maskable")})
        self.assertTrue(m["shortcuts"])
        from django.contrib.staticfiles import finders

        for icon in m["icons"] + [i for sc in m["shortcuts"] for i in sc["icons"]]:
            self.assertTrue(finders.find(icon["src"].removeprefix("/static/")), icon["src"])  # ไฟล์ไอคอนมีอยู่จริง

    def test_service_worker_precaches_offline_and_has_scope_root(self):
        r = self.client.get(reverse("core:sw"))
        self.assertEqual(r["Content-Type"], "application/javascript")
        self.assertIn("no-cache", r["Cache-Control"])
        self.assertIn(reverse("core:offline"), r.content.decode())

    def test_offline_page_has_no_user_data(self):
        """หน้านี้ถูก cache ใน SW ให้ทุกคนใช้ร่วมกัน ห้ามมีชื่อ/อีเมล/เมนูของผู้ใช้"""
        u = User.objects.create_user("secret@x.com", "pw-12345678", full_name="ลับมาก", phone="0811111111")
        self.client.force_login(u)
        html = self.client.get(reverse("core:offline")).content.decode()
        self.assertNotIn("ลับมาก", html)
        self.assertNotIn("secret@x.com", html)
        self.assertNotIn("csrfmiddlewaretoken", html)

    def test_pages_link_manifest_and_install_button(self):
        html = self.client.get(reverse("core:home")).content.decode()
        self.assertIn('rel="manifest"', html)
        self.assertIn("data-pwa-install", html)


class LegalPagesTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_pages_render_public_and_in_sitemap(self):
        for name in ("core:privacy", "core:terms"):
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 200, name)
            self.assertContains(r, "อัปเดตล่าสุด")
        sm = self.client.get("/sitemap.xml").content.decode()
        self.assertIn(reverse("core:privacy"), sm)
        self.assertIn(reverse("core:terms"), sm)

    def test_privacy_covers_cookies_and_third_parties(self):
        html = self.client.get(reverse("core:privacy")).content.decode()
        for needle in ('id="cookies"', "lmh_consent", "sessionid", "EasySlip", "Telegram", "YouTube", "สิทธิ์ของคุณ", "ต่ำกว่า 20 ปี"):
            self.assertIn(needle, html, needle)

    def test_owner_and_contact_come_from_settings(self):
        r = self.client.get(reverse("core:privacy"))
        self.assertContains(r, "Let Me Help")  # ยังไม่ตั้งชื่อ → ใช้ชื่อเว็บ ไม่ปล่อยช่องว่าง/placeholder
        SiteSetting.objects.create(key="OWNER_NAME", value="สมชาย ใจดี")
        SiteSetting.objects.create(key="CONTACT_EMAIL", value="hello@example.com")
        cache.clear()
        r = self.client.get(reverse("core:terms"))
        self.assertContains(r, "สมชาย ใจดี")
        self.assertContains(r, "mailto:hello@example.com")

    def test_terms_mention_key_business_rules(self):
        html = self.client.get(reverse("core:terms")).content.decode()
        for needle in ("365 วัน", "PromptPay", "ไม่คืนเงิน", "Shopee", "ห้ามแชร์"):
            self.assertIn(needle, html, needle)


class RegisterConsentTests(TestCase):
    DATA = {"full_name": "สมหญิง", "phone": "0812345678", "email": "som@x.com", "password1": "Zq9!pLmw-4471", "password2": "Zq9!pLmw-4471"}

    def test_must_accept_terms_and_acceptance_is_recorded(self):
        r = self.client.post(reverse("accounts:register"), self.DATA)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "กรุณายอมรับข้อกำหนด")
        self.assertFalse(User.objects.filter(email="som@x.com").exists())
        r = self.client.post(reverse("accounts:register"), {**self.DATA, "accept_terms": "on"})
        self.assertEqual(r.status_code, 302)
        self.assertIsNotNone(User.objects.get(email="som@x.com").terms_accepted_at)

    def test_register_page_links_to_policies(self):
        html = self.client.get(reverse("accounts:register")).content.decode()
        self.assertIn(reverse("core:terms"), html)
        self.assertIn(reverse("core:privacy"), html)


class FooterAndCookieBannerTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_footer_has_legal_links_and_cookie_settings(self):
        html = self.client.get(reverse("courses:list")).content.decode()
        self.assertIn(reverse("core:privacy"), html)
        self.assertIn(reverse("core:terms"), html)
        self.assertIn("data-cookie-settings", html)
        self.assertIn('id="cookieBanner"', html)
        self.assertIn("consent.js", html)

    def test_brand_socials_are_shown_by_default(self):
        html = self.client.get(reverse("core:home")).content.decode()
        self.assertIn("https://www.tiktok.com/@letmehelp.eng", html)
        self.assertIn("https://www.facebook.com/share/1CJVxPAg1N/", html)
        self.assertNotIn("_t=", html)  # ไม่เอา tracking param จากลิงก์แชร์
        self.assertNotIn('aria-label="Instagram"', html)  # ยังไม่มีลิงก์ = ไม่แสดงไอคอน

    @override_settings(SOCIAL_FACEBOOK="", SOCIAL_TIKTOK="")
    def test_social_icons_only_for_links_that_are_set(self):
        html = self.client.get(reverse("core:home")).content.decode()
        self.assertNotIn('aria-label="Facebook"', html)
        SiteSetting.objects.create(key="SOCIAL_FACEBOOK", value="https://facebook.com/letmehelp")
        SiteSetting.objects.create(key="SOCIAL_TIKTOK", value="https://tiktok.com/@letmehelp")
        cache.clear()
        html = self.client.get(reverse("core:home")).content.decode()
        self.assertIn("https://facebook.com/letmehelp", html)
        self.assertIn("https://tiktok.com/@letmehelp", html)
        self.assertNotIn('aria-label="Instagram"', html)
        self.assertIn('rel="noopener noreferrer me"', html)

    def test_admin_dashboard_has_no_cookie_banner(self):
        a = User.objects.create_user("a@x.com", "pw-12345678", full_name="A", phone="0800000000", is_staff=True)
        self.client.force_login(a)
        self.assertNotContains(self.client.get(reverse("dashboard:overview")), 'id="cookieBanner"')

    def test_settings_form_saves_owner_contact_and_socials(self):
        a = User.objects.create_user("a@x.com", "pw-12345678", full_name="A", phone="0800000000", is_staff=True)
        self.client.force_login(a)
        data = {"PROMPTPAY_ID": "", "PROMPTPAY_ACCOUNT_NAME": "", "LINE_CONTACT_URL": "", "EXPIRY_REMINDER_DAYS": "30,7,1", "ANNOUNCEMENT": "",
                "OWNER_NAME": "สมชาย", "CONTACT_EMAIL": "me@x.com", "SOCIAL_FACEBOOK": "https://facebook.com/x", "SOCIAL_INSTAGRAM": "", "SOCIAL_YOUTUBE": "", "SOCIAL_TIKTOK": ""}
        self.assertEqual(self.client.post(reverse("dashboard:site_settings"), data).status_code, 302)
        self.assertContains(self.client.get(reverse("core:home")), "https://facebook.com/x")
        self.assertContains(self.client.get(reverse("core:privacy")), "me@x.com")

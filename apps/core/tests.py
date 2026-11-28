"""Smoke + business-rule tests (รัน: python manage.py test)"""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.courses.models import Category, Course, CoursePackage, Lesson, Section
from apps.enrollments.models import Enrollment
from apps.enrollments.services import enrollment_service
from apps.learning.models import LessonNote, LessonProgress, StudyLog
from apps.learning.services import progress_service
from apps.notifications.tasks import process_enrollment_expiry
from apps.payments.models import Order, PaymentSlip
from apps.payments.services import order_service, promptpay, slip_verification_service
from apps.payments.services.easyslip_client import SlipData
from apps.courses.services.pricing_service import packages_for, pick_package
from apps.courses.services.youtube import extract_youtube_id

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82")


def make_course(price=500, days=30):
    cat = Category.objects.create(name="TGAT", slug="tgat")
    course = Course.objects.create(category=cat, title="C", slug="c", price=price, access_days=days, is_published=True)
    sec = Section.objects.create(course=course, title="S", order=1)
    lesson = Lesson.objects.create(section=sec, title="L", youtube_video_id="M7lc1UVf-VE", duration_seconds=100, order=1)
    return course, lesson


class BaseCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("s@x.com", "pw-12345678", full_name="S", phone="0811111111")
        self.course, self.lesson = make_course()


class YoutubeTests(TestCase):
    def test_extract(self):
        vid = "M7lc1UVf-VE"
        for v in [vid, f"https://youtu.be/{vid}", f"https://www.youtube.com/watch?v={vid}&t=3", f"https://www.youtube.com/embed/{vid}"]:
            self.assertEqual(extract_youtube_id(v), vid)
        self.assertIsNone(extract_youtube_id("https://example.com"))


class PromptPayTests(TestCase):
    def test_payload_crc_and_amount(self):
        p = promptpay.build_payload("0812345678", Decimal("100.00"))
        self.assertIn("0066812345678", p)
        self.assertIn("5406100.00", p)
        body, crc = p[:-4], p[-4:]
        self.assertEqual(promptpay._crc16(body), crc)
        self.assertTrue(promptpay.qr_svg("0812345678", Decimal("100")).startswith("<svg"))


class EnrollmentTests(BaseCase):
    def test_extend_keeps_remaining_days(self):
        e1 = enrollment_service.grant_or_extend(user=self.user, course=self.course)
        first_exp = e1.expires_at
        e2 = enrollment_service.grant_or_extend(user=self.user, course=self.course)
        self.assertEqual(e2.expires_at, first_exp + timedelta(days=30))
        self.assertEqual(Enrollment.objects.count(), 1)

    def test_renew_after_expiry_counts_from_now(self):
        e = enrollment_service.grant_or_extend(user=self.user, course=self.course)
        Enrollment.objects.filter(pk=e.pk).update(expires_at=timezone.now() - timedelta(days=5), status="expired")
        e = enrollment_service.grant_or_extend(user=self.user, course=self.course)
        self.assertAlmostEqual((e.expires_at - timezone.now()).days, 29, delta=1)
        self.assertEqual(e.status, "active")


class PaymentFlowTests(BaseCase):
    def _slip(self, order):
        return PaymentSlip.objects.create(order=order, image=SimpleUploadedFile("s.png", PNG, "image/png"))

    @override_settings(EASYSLIP_API_KEY="k", PROMPTPAY_BANK_ACCOUNT="", PROMPTPAY_ID="0812345678", PROMPTPAY_ACCOUNT_NAME="")
    def test_auto_verify_success_and_duplicate(self):
        order = order_service.get_or_create_pending_order(user=self.user, course=self.course, package=pick_package(self.course, None))
        data = SlipData("REF1", Decimal("500"), [], ["xxx-xxx-5678"], {"ok": 1})
        with mock.patch.object(slip_verification_service, "verify_slip_image", return_value=data):
            s1 = self._slip(order)
            self.assertEqual(slip_verification_service.verify_slip(s1.pk), "verified")
            order.refresh_from_db()
            self.assertEqual(order.status, "paid")
            self.assertTrue(Enrollment.objects.filter(user=self.user, course=self.course).exists())
            # ใช้สลิปเดิมกับออเดอร์ใหม่ → ต้องถูกปฏิเสธ
            o2 = Order.objects.create(user=self.user, course=self.course, amount=500)
            s2 = self._slip(o2)
            self.assertEqual(slip_verification_service.verify_slip(s2.pk), "rejected")
            s2.refresh_from_db()
            self.assertIn("ใช้งานแล้ว", s2.reason)

    @override_settings(EASYSLIP_API_KEY="k", PROMPTPAY_BANK_ACCOUNT="", PROMPTPAY_ID="0812345678")
    def test_wrong_amount_and_wrong_receiver_go_to_manual_review(self):
        order = order_service.get_or_create_pending_order(user=self.user, course=self.course, package=pick_package(self.course, None))
        with mock.patch.object(slip_verification_service, "verify_slip_image",
                               return_value=SlipData("R2", Decimal("100"), [], ["xxx-xxx-5678"], {})):
            s1 = self._slip(order)
            self.assertEqual(slip_verification_service.verify_slip(s1.pk), "manual_review")
            s1.refresh_from_db()
            self.assertIn("ยอดไม่ตรง", s1.reason)
            self.assertEqual(s1.trans_ref, "R2")  # เก็บเลขอ้างอิงไว้กันนำสลิปเดิมมาใช้ซ้ำ
        with mock.patch.object(slip_verification_service, "verify_slip_image",
                               return_value=SlipData("R3", Decimal("500"), [], ["xxx-xxx-9999"], {})):
            s2 = self._slip(order)
            self.assertEqual(slip_verification_service.verify_slip(s2.pk), "manual_review")
            s2.refresh_from_db()
            self.assertIn("ผู้รับเงินไม่ตรง", s2.reason)
        self.assertFalse(Enrollment.objects.exists())  # ยังไม่เปิดสิทธิ์จนกว่าแอดมินอนุมัติ

    @override_settings(EASYSLIP_API_KEY="")
    def test_without_api_key_goes_to_manual_review_then_admin_approves(self):
        order = order_service.get_or_create_pending_order(user=self.user, course=self.course, package=pick_package(self.course, None))
        slip = self._slip(order)
        self.assertEqual(slip_verification_service.verify_slip(slip.pk), "manual_review")
        admin = User.objects.create_user("a@x.com", "pw-12345678", full_name="A", phone="0822222222", is_staff=True)
        order_service.approve_slip_manually(slip_id=slip.pk, admin=admin)
        order_service.approve_slip_manually(slip_id=slip.pk, admin=admin)  # เรียกซ้ำต้องไม่เปิดสิทธิ์ซ้ำ
        self.assertEqual(Enrollment.objects.count(), 1)

    def test_upload_view_triggers_task(self):
        self.client.force_login(self.user)
        order = order_service.get_or_create_pending_order(user=self.user, course=self.course, package=pick_package(self.course, None))
        with mock.patch("apps.payments.tasks.verify_slip_task.delay") as delay, self.captureOnCommitCallbacks(execute=True):
            r = self.client.post(reverse("payments:upload_slip", args=[order.pk]),
                                 {"image": SimpleUploadedFile("s.png", PNG, "image/png")})
        self.assertEqual(r.status_code, 200)
        delay.assert_called_once()


class ProgressTests(BaseCase):
    def test_rewind_and_study_log(self):
        self.assertEqual(progress_service.resume_position(5), 0)
        self.assertEqual(progress_service.resume_position(65), 55)
        progress_service.save_progress(user=self.user, lesson=self.lesson, position=50, watched_delta=999)
        self.assertEqual(StudyLog.objects.get().seconds, progress_service.MAX_DELTA)
        progress_service.save_progress(user=self.user, lesson=self.lesson, position=95, watched_delta=10)
        p = LessonProgress.objects.get()
        self.assertTrue(p.completed)
        self.assertEqual(StudyLog.objects.get().seconds, progress_service.MAX_DELTA + 10)

    def test_progress_endpoint_requires_enrollment(self):
        self.client.force_login(self.user)
        url = reverse("learning:save_progress")
        body = {"lesson_id": self.lesson.pk, "position": 10, "delta": 5}
        r = self.client.post(url, body, content_type="application/json")
        self.assertEqual(r.status_code, 403)
        enrollment_service.grant_or_extend(user=self.user, course=self.course)
        r = self.client.post(url, body, content_type="application/json")
        self.assertEqual(r.status_code, 200)

    def test_student_pages_render(self):
        """แดชบอร์ด/สถิติ/หน้าเรียน render ได้ทั้งตอนยังไม่มีคอร์สและหลังได้สิทธิ์ (กัน template พังหลังปรับดีไซน์)"""
        self.client.force_login(self.user)
        for name in ("learning:my_courses", "learning:study"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        enrollment_service.grant_or_extend(user=self.user, course=self.course)
        progress_service.save_progress(user=self.user, lesson=self.lesson, position=30, watched_delta=10)
        r = self.client.get(reverse("learning:my_courses"))
        self.assertContains(r, "เรียนต่อจากที่ค้างไว้")
        self.assertContains(r, self.course.title)
        self.assertEqual(self.client.get(reverse("learning:study")).status_code, 200)
        self.assertEqual(self.client.get(reverse("learning:player", args=["c"])).status_code, 200)

    def test_player_redirects_when_not_enrolled(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse("learning:player", args=["c"]))
        self.assertRedirects(r, reverse("payments:checkout", args=["c"]), fetch_redirect_response=False)


class ExpiryTests(BaseCase):
    def test_reminder_sent_once_and_expiry_closed(self):
        e = enrollment_service.grant_or_extend(user=self.user, course=self.course)
        Enrollment.objects.filter(pk=e.pk).update(expires_at=timezone.now() + timedelta(days=6, hours=12))  # อยู่ในช่วงเตือน 7 วัน (ค่าเริ่มต้น 30/7/1)
        from django.core import mail
        process_enrollment_expiry()
        process_enrollment_expiry()  # รอบสอง ห้ามส่งซ้ำ
        self.assertEqual(len(mail.outbox), 1)
        Enrollment.objects.filter(pk=e.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        process_enrollment_expiry()
        e.refresh_from_db()
        self.assertEqual(e.status, "expired")


class AccessControlTests(BaseCase):
    def test_dashboard_requires_staff(self):
        url = reverse("dashboard:overview")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 302)  # นักเรียนเข้าไม่ได้
        self.user.is_staff = True
        self.user.save()
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_public_pages(self):
        for name, args in [("core:home", []), ("courses:list", []), ("courses:detail", ["c"]),
                           ("accounts:login", []), ("accounts:register", []), ("core:manifest", []),
                           ("core:sw", []), ("core:robots", [])]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)
        self.assertEqual(self.client.get("/sitemap.xml").status_code, 200)

    def test_list_query_counts_are_constant(self):
        for i in range(5):
            Course.objects.create(category=self.course.category, title=f"x{i}", slug=f"x{i}", price=1, is_published=True)
        with self.assertNumQueries(3):  # count + categories + courses (ไม่ขึ้นกับจำนวนคอร์ส)
            self.client.get(reverse("courses:list"))


class PackageTests(BaseCase):
    def test_packages_sorted_and_default_included(self):
        CoursePackage.objects.create(course=self.course, label="ตลอดชีพ", days=36500, price=2000)
        CoursePackage.objects.create(course=self.course, label="1 ปี", days=365, price=1200)
        CoursePackage.objects.create(course=self.course, label="ปิด", days=90, price=1, is_active=False)
        pk = packages_for(Course.objects.prefetch_related("packages").get(pk=self.course.pk))
        self.assertEqual([p.days for p in pk], [30, 365, 36500])
        self.assertTrue(pk[-1].is_lifetime)
        self.assertEqual(pick_package(self.course, "999").days, 30)  # วันที่ไม่มีอยู่ → ใช้แพ็กเกจแรก

    def test_paid_order_grants_package_duration(self):
        CoursePackage.objects.create(course=self.course, label="1 ปี", days=365, price=1200)
        course = Course.objects.prefetch_related("packages").get(pk=self.course.pk)
        order = order_service.get_or_create_pending_order(user=self.user, course=course, package=pick_package(course, 365))
        self.assertEqual((order.amount, order.duration_days), (Decimal("1200"), 365))
        order_service.mark_paid(order_id=order.pk)
        enr = Enrollment.objects.get()
        self.assertAlmostEqual((enr.expires_at - timezone.now()).days, 365, delta=1)

    def test_checkout_page_lists_packages_and_reuses_review_order(self):
        CoursePackage.objects.create(course=self.course, label="1 ปี", days=365, price=1200)
        self.client.force_login(self.user)
        r = self.client.get(reverse("payments:checkout", args=["c"]) + "?days=365")
        self.assertContains(r, "เลือกแพ็กเกจ")
        order = Order.objects.get()
        self.assertEqual(order.amount, Decimal("1200"))
        Order.objects.filter(pk=order.pk).update(status="reviewing")
        self.client.get(reverse("payments:checkout", args=["c"]))
        self.assertEqual(Order.objects.count(), 1)  # ไม่สร้างออเดอร์ซ้ำขณะกำลังตรวจสลิป


class NoteAndPreviewTests(BaseCase):
    def test_note_requires_enrollment_and_saves(self):
        self.client.force_login(self.user)
        url = reverse("learning:note", args=[self.lesson.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        enrollment_service.grant_or_extend(user=self.user, course=self.course)
        r = self.client.post(url, {"content": "[01:05] สำคัญ"}, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get(url).json()["content"], "[01:05] สำคัญ")
        self.client.post(url, {"content": "x" * 30000}, content_type="application/json")
        self.assertEqual(len(LessonNote.objects.get().content), 20000)

    def test_free_preview_open_to_anonymous_but_locked_otherwise(self):
        l2 = Lesson.objects.create(section=self.lesson.section, title="L2", youtube_video_id="M7lc1UVf-VE", order=2, is_free_preview=True)
        self.assertEqual(self.client.get(reverse("learning:player_lesson", args=["c", l2.pk])).status_code, 200)
        r = self.client.get(reverse("learning:player_lesson", args=["c", self.lesson.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r["Location"])
        r = self.client.get(reverse("core:free_trial"))
        self.assertContains(r, "L2")
        self.assertEqual(self.client.get(reverse("core:guide")).status_code, 200)

    def test_study_stats_longest_streak(self):
        from datetime import timedelta as td
        from apps.learning.selectors.learning_selector import study_stats
        today = timezone.localdate()
        for d in (0, 1, 2, 5, 6, 7, 8):
            StudyLog.objects.create(user=self.user, lesson=self.lesson, date=today - td(days=d), seconds=60)
        st = study_stats(self.user)
        self.assertEqual((st["streak"], st["longest_streak"], st["studied_today"]), (3, 4, True))


class CoverTests(BaseCase):
    def test_cover_priority(self):
        from apps.core.templatetags.ui import course_cover
        c = Course.objects.get(pk=self.course.pk)
        self.assertEqual(course_cover(c), "")
        c.first_video_id = "M7lc1UVf-VE"
        self.assertIn("i.ytimg.com/vi/M7lc1UVf-VE", course_cover(c))
        c.cover_url = "https://example.com/a.jpg"
        self.assertEqual(course_cover(c), "https://example.com/a.jpg")
        c.cover_url = "/static/img/covers/tgat.jpg"
        self.assertTrue(course_cover(c).endswith("img/covers/tgat.jpg"))

    def test_auto_cover_never_uses_a_paid_lesson_video(self):
        """ภาพปกจาก YouTube มี video id ใน URL — ห้ามใช้คลิปที่ต้องซื้อ (หน้ารายการคอร์สเปิดให้ทุกคน)"""
        from apps.courses.selectors.course_selector import featured_courses
        self.assertIsNone(featured_courses()[0].first_video_id)
        self.assertNotContains(self.client.get(reverse("courses:list")), "M7lc1UVf-VE")
        Lesson.objects.create(section=self.lesson.section, title="Free", youtube_video_id="FREEvid0001", order=2, is_free_preview=True)
        self.assertEqual(featured_courses()[0].first_video_id, "FREEvid0001")


class ProtectedPlayerTests(BaseCase):
    def test_player_page_has_shield_and_watermark(self):
        enrollment_service.grant_or_extend(user=self.user, course=self.course)
        self.client.force_login(self.user)
        r = self.client.get(reverse("learning:player_lesson", args=["c", self.lesson.pk]))
        self.assertContains(r, 'id="pl-shield"')
        self.assertContains(r, 'class="pl-wm"')
        self.assertContains(r, "s@x.com")
        self.assertContains(r, "is-protected")

    def test_free_preview_for_anonymous_has_no_watermark(self):
        l2 = Lesson.objects.create(section=self.lesson.section, title="L2", youtube_video_id="M7lc1UVf-VE", order=2, is_free_preview=True)
        r = self.client.get(reverse("learning:player_lesson", args=["c", l2.pk]))
        self.assertContains(r, 'id="pl-shield"')
        self.assertNotContains(r, 'class="pl-wm"')


class SeoAeoTests(BaseCase):
    """schema.org JSON-LD ถูกต้อง (parse ได้) + หน้าเกี่ยวกับเรา + llms.txt"""

    def _graph(self, url):
        import json
        import re

        html = self.client.get(url).content.decode()
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        self.assertTrue(blocks, url)
        nodes = []
        for b in blocks:
            data = json.loads(b)
            nodes += data.get("@graph", [data])
        return {n["@type"]: n for n in nodes}

    def test_home_has_organization_website_person_faq(self):
        g = self._graph(reverse("core:home"))
        self.assertEqual(set(g) >= {"EducationalOrganization", "WebSite", "Person", "FAQPage"}, True, g.keys())
        self.assertIn("https://www.youtube.com/@letmehelp.eng4848", g["EducationalOrganization"]["sameAs"])
        self.assertEqual(g["Person"]["alumniOf"]["name"], "จุฬาลงกรณ์มหาวิทยาลัย")

    def test_course_page_has_course_offer_instance_and_breadcrumbs(self):
        g = self._graph(reverse("courses:detail", args=["c"]))
        c = g["Course"]
        self.assertEqual((c["offers"][0]["price"], c["offers"][0]["priceCurrency"]), ("500.00", "THB"))
        self.assertEqual(c["hasCourseInstance"][0]["courseMode"], "Online")
        self.assertEqual(c["hasCourseInstance"][0]["courseWorkload"], "PT2M")  # คลิป 100 วินาที
        self.assertEqual(len(g["BreadcrumbList"]["itemListElement"]), 3)
        self.assertIn("ItemList", self._graph(reverse("courses:list")))

    def test_about_page_answers_first_with_live_price(self):
        r = self.client.get(reverse("core:about"))
        self.assertContains(r, "พี่ใยไหมคือผู้สอนและผู้ก่อตั้ง Let Me Help")
        self.assertContains(r, "฿500")
        self.assertIn("AboutPage", self._graph(reverse("core:about")))
        self.assertIn("FAQPage", self._graph(reverse("core:guide")))

    def test_llms_txt_and_full(self):
        r = self.client.get("/llms.txt")
        self.assertTrue(r["Content-Type"].startswith("text/markdown"))
        body = r.content.decode()
        self.assertTrue(body.startswith("# Let Me Help"))
        self.assertIn("ราคา 500 บาท", body)
        self.assertNotIn("M7lc1UVf-VE", body)  # ไม่เผย video id
        full = self.client.get("/llms-full.txt").content.decode()
        self.assertIn("สารบัญ:", full)
        self.assertIn("   - L", full)
        self.assertEqual(self.client.get("/llm.txt").status_code, 301)

    def test_sitemap_lists_about(self):
        self.assertContains(self.client.get("/sitemap.xml"), "/about/")


class ReferrerPolicyTests(BaseCase):
    def test_youtube_embed_gets_origin_referrer(self):
        """YouTube Error 153 ถ้าไม่ส่ง Referer — ต้องเป็น strict-origin-when-cross-origin ไม่ใช่ same-origin"""
        r = self.client.get(reverse("core:home"))
        self.assertEqual(r["Referrer-Policy"], "strict-origin-when-cross-origin")

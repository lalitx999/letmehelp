"""ทดสอบหลังบ้าน: สิทธิ์เข้าถึง · ถังขยะ · ประวัติ · สิทธิ์เรียน · ออเดอร์ · อนุมัติสลิปอัตโนมัติ"""
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.services import account_service
from apps.core.exceptions import ActionError
from apps.core.models import AuditLog, SiteSetting
from apps.core.services import settings_service
from apps.core.tests import PNG, make_course
from apps.courses.models import Category, Course, Lesson, Section
from apps.dashboard.services import trash_service
from apps.enrollments.models import Enrollment
from apps.enrollments.services import enrollment_service
from apps.payments.models import Order, PaymentSlip
from apps.payments.services import order_service, slip_verification_service
from apps.payments.services.easyslip_client import SlipData
from apps.courses.services.pricing_service import pick_package


class DashCase(TestCase):
    def setUp(self):
        cache.clear()  # แคชตั้งค่าเว็บไม่ถูกม้วนกลับพร้อมฐานข้อมูล
        self.addCleanup(cache.clear)
        self.admin = User.objects.create_user("a@x.com", "pw-12345678", full_name="Admin", phone="0800000000", is_staff=True)
        self.student = User.objects.create_user("s@x.com", "pw-12345678", full_name="Stu", phone="0811111111")
        self.course, self.lesson = make_course()
        self.req = RequestFactory().post("/")
        self.req.user = self.admin
        self.req.META["REMOTE_ADDR"] = "127.0.0.1"


class AccessMatrixTests(DashCase):
    def urls(self):
        order = Order.objects.create(user=self.student, course=self.course, amount=500)
        enr = enrollment_service.grant_or_extend(user=self.student, course=self.course)
        return [
            reverse("dashboard:overview"), reverse("dashboard:category_list"), reverse("dashboard:category_add"),
            reverse("dashboard:course_list"), reverse("dashboard:course_add"),
            reverse("dashboard:course_edit", args=[self.course.pk]), reverse("dashboard:course_content", args=[self.course.pk]),
            reverse("dashboard:section_add", args=[self.course.pk]), reverse("dashboard:lesson_add", args=[self.lesson.section_id]),
            reverse("dashboard:lesson_edit", args=[self.lesson.pk]), reverse("dashboard:package_add", args=[self.course.pk]),
            reverse("dashboard:student_list"), reverse("dashboard:student_add"),
            reverse("dashboard:student_detail", args=[self.student.pk]), reverse("dashboard:student_edit", args=[self.student.pk]),
            reverse("dashboard:user_password", args=[self.student.pk]),
            reverse("dashboard:enrollment_list"), reverse("dashboard:enrollment_grant"), reverse("dashboard:enrollment_extend", args=[enr.pk]),
            reverse("dashboard:order_list"), reverse("dashboard:order_add"), reverse("dashboard:order_detail", args=[order.pk]),
            reverse("dashboard:exports"),
            reverse("dashboard:admin_list"), reverse("dashboard:admin_add"), reverse("dashboard:site_settings"),
            reverse("dashboard:audit_list"), reverse("dashboard:trash"),
        ]

    def test_anonymous_and_student_are_redirected_admin_gets_200(self):
        urls = self.urls()
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302, f"anonymous {url}")
        self.client.force_login(self.student)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302, f"student {url}")
        self.client.force_login(self.admin)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200, f"admin {url}")

    def test_old_slip_page_redirects_to_payment_review_tab(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse("dashboard:slip_list"))
        self.assertRedirects(r, reverse("dashboard:order_list") + "?tab=review")

    def test_post_actions_blocked_for_student(self):
        self.client.force_login(self.student)
        r = self.client.post(reverse("dashboard:course_delete", args=[self.course.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Course.objects.filter(pk=self.course.pk).exists())


class OverviewTests(DashCase):
    def test_overview_bento_shows_sales_todo_and_slip_badge(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse("dashboard:overview"))
        self.assertContains(r, "ไม่มีงานค้าง")
        self.assertNotContains(r, 'class="adm-badge"')
        Order.objects.create(user=self.student, course=self.course, amount=990, status=Order.Status.PAID, paid_at=timezone.now())
        pending = Order.objects.create(user=self.student, course=self.course, amount=990)
        PaymentSlip.objects.create(order=pending, image=SimpleUploadedFile("s.png", PNG, "image/png"), status=PaymentSlip.Status.MANUAL_REVIEW)
        r = self.client.get(reverse("dashboard:overview"))
        self.assertContains(r, "สลิปรอแอดมินตรวจ")
        self.assertContains(r, '<b class="adm-badge">1</b>', html=False)
        self.assertContains(r, self.course.title)  # คอร์สขายดี
        self.assertContains(r, "฿990")

    def test_slip_badge_query_only_on_admin_pages(self):
        self.client.force_login(self.admin)
        with CaptureQueriesContext(connection) as ctx:
            self.client.get(reverse("courses:list"))
        self.assertFalse(any("payments_paymentslip" in q["sql"] for q in ctx.captured_queries))


class TrashTests(DashCase):
    def test_delete_hides_from_public_restore_brings_back(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse("dashboard:course_delete", args=[self.course.pk]), HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        self.assertFalse(Course.objects.filter(pk=self.course.pk).exists())
        self.assertTrue(Course.all_objects.filter(pk=self.course.pk, deleted_at__isnull=False).exists())
        self.assertEqual(self.client.get(reverse("courses:detail", args=["c"])).status_code, 404)
        self.assertContains(self.client.get(reverse("dashboard:trash")), self.course.title)
        self.client.post(reverse("dashboard:trash_restore", args=["course", self.course.pk]), HTTP_X_REQUESTED_WITH="fetch")
        c = Course.objects.get(pk=self.course.pk)
        self.assertFalse(c.is_published)  # กู้คืนเป็นฉบับร่าง ไม่เผยแพร่เอง

    def test_enrolled_student_keeps_learning_after_course_deleted(self):
        enrollment_service.grant_or_extend(user=self.student, course=self.course)
        from apps.courses.services import catalog_service

        catalog_service.delete_course(Course.objects.get(pk=self.course.pk), self.req)
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("learning:player", args=["c"])).status_code, 200)
        other = User.objects.create_user("o@x.com", "pw-12345678", full_name="O", phone="0833333333")
        self.client.force_login(other)
        self.assertNotEqual(self.client.get(reverse("learning:player", args=["c"])).status_code, 200)

    def test_purge_blocked_when_course_has_students_and_allowed_otherwise(self):
        enrollment_service.grant_or_extend(user=self.student, course=self.course)
        Course.objects.get(pk=self.course.pk).soft_delete()
        with self.assertRaises(ActionError):
            trash_service.purge("course", self.course.pk, self.req)
        Enrollment.objects.all().delete()
        trash_service.purge("course", self.course.pk, self.req)
        self.assertFalse(Course.all_objects.filter(pk=self.course.pk).exists())
        self.assertTrue(AuditLog.objects.filter(action="purge").exists())

    def test_category_with_courses_cannot_be_deleted(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse("dashboard:category_delete", args=[self.course.category_id]), HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()["ok"])
        self.assertTrue(Category.objects.filter(pk=self.course.category_id).exists())

    def test_deleted_lesson_not_counted_and_not_listed(self):
        from apps.courses.services import catalog_service
        from apps.courses.selectors import course_selector

        Lesson.objects.create(section=self.lesson.section, title="L2", youtube_video_id="M7lc1UVf-VE", order=2)
        catalog_service.delete_lesson(Lesson.objects.get(title="L2"), self.req)
        row = next(c for c in course_selector.dashboard_course_list() if c.pk == self.course.pk)
        self.assertEqual(row.lesson_count, 1)


class AuditTests(DashCase):
    def test_actions_write_audit_with_actor(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("dashboard:course_toggle", args=[self.course.pk, "is_featured"]), HTTP_X_REQUESTED_WITH="fetch")
        self.client.post(reverse("dashboard:course_delete", args=[self.course.pk]), HTTP_X_REQUESTED_WITH="fetch")
        log = AuditLog.objects.filter(model="Course")
        self.assertEqual({a.action for a in log}, {"update", "delete"})
        self.assertTrue(all(a.user_id == self.admin.pk for a in log))
        self.assertContains(self.client.get(reverse("dashboard:audit_list")), "delete")


class EnrollmentAdminTests(DashCase):
    def test_grant_extend_revoke_restore(self):
        e = enrollment_service.grant_manual(user=self.student, course=self.course, days=10, source="manual", note="ชดเชย", request=self.req)
        self.assertEqual((e.source, e.granted_by_id, e.note), ("manual", self.admin.pk, "ชดเชย"))
        before = e.expires_at
        enrollment_service.extend(e, self.req, add_days=5)
        e.refresh_from_db()
        self.assertEqual((e.expires_at - before).days, 5)
        enrollment_service.revoke(e, self.req)
        e.refresh_from_db()
        self.assertEqual(e.status, "cancelled")
        from apps.enrollments.selectors.enrollment_selector import get_active_enrollment

        self.assertIsNone(get_active_enrollment(self.student, self.course.pk))
        enrollment_service.restore(e, self.req)
        e.refresh_from_db()
        self.assertEqual(e.status, "active")
        self.assertIsNotNone(get_active_enrollment(self.student, self.course.pk))
        self.assertEqual(set(AuditLog.objects.values_list("action", flat=True)), {"grant", "extend", "revoke", "restore"})

    def test_grant_via_modal_post(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse("dashboard:enrollment_grant"),
                             {"email": "s@x.com", "course": self.course.pk, "days": 30, "source": "comp", "note": "ทุน"},
                             HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(Enrollment.objects.get().source, "comp")
        r = self.client.post(reverse("dashboard:enrollment_grant"),
                             {"email": "nobody@x.com", "course": self.course.pk, "days": 30, "source": "comp"},
                             HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(r.status_code, 422)


class OrderAdminTests(DashCase):
    def test_manual_order_paid_is_idempotent_and_grants_once(self):
        o = order_service.create_manual_order(user=self.student, course=self.course, amount=Decimal("300"), days=20, note="เงินสด", paid=True, request=self.req)
        self.assertEqual(o.source, "manual")
        o.refresh_from_db()
        self.assertEqual(o.status, "paid")
        self.assertEqual(Enrollment.objects.count(), 1)
        with self.assertRaises(ActionError):
            order_service.mark_paid_manually(o, self.req)
        self.assertEqual(Enrollment.objects.count(), 1)

    def test_mark_paid_manually_pending(self):
        o = Order.objects.create(user=self.student, course=self.course, amount=500)
        order_service.mark_paid_manually(o, self.req)
        order_service.mark_paid(order_id=o.pk)  # เรียกซ้ำเงียบๆ ต้องไม่ต่ออายุซ้ำ
        self.assertEqual(Enrollment.objects.count(), 1)
        e = Enrollment.objects.get()
        self.assertAlmostEqual((e.expires_at - timezone.now()).days, 30, delta=1)

    def test_cancel_and_refund_rules(self):
        pending = Order.objects.create(user=self.student, course=self.course, amount=500)
        order_service.cancel_order(pending, self.req)
        pending.refresh_from_db()
        self.assertEqual(pending.status, "cancelled")
        with self.assertRaises(ActionError):
            order_service.refund_order(pending, self.req, revoke_access=False)
        paid = order_service.create_manual_order(user=self.student, course=self.course, amount=Decimal("100"), days=5, note="", paid=True, request=self.req)
        paid.refresh_from_db()
        with self.assertRaises(ActionError):
            order_service.cancel_order(paid, self.req)
        order_service.refund_order(paid, self.req, revoke_access=True, note="ขอคืน")
        paid.refresh_from_db()
        self.assertEqual(paid.status, "refunded")
        self.assertEqual(Enrollment.objects.get().status, "cancelled")


class SlipAutoApprovalTests(DashCase):
    def _slip(self, order):
        return PaymentSlip.objects.create(order=order, image=SimpleUploadedFile("s.png", PNG, "image/png"))

    @override_settings(EASYSLIP_API_KEY="k", PROMPTPAY_BANK_ACCOUNT="", PROMPTPAY_ID="", PROMPTPAY_ACCOUNT_NAME="")
    def test_amount_matches_without_shop_account_is_auto_approved(self):
        order = order_service.get_or_create_pending_order(user=self.student, course=self.course, package=pick_package(self.course, None))
        with mock.patch.object(slip_verification_service, "verify_slip_image", return_value=SlipData("AUTO1", Decimal("500"), [], ["xxx-1234"], {})):
            self.assertEqual(slip_verification_service.verify_slip(self._slip(order).pk), "verified")
        order.refresh_from_db()
        self.assertEqual(order.status, "paid")
        self.assertTrue(Enrollment.objects.filter(user=self.student, course=self.course).exists())
        log = AuditLog.objects.get(action="approve")
        self.assertIn("EasySlip", log.actor_label)

    @override_settings(EASYSLIP_API_KEY="k", PROMPTPAY_BANK_ACCOUNT="", PROMPTPAY_ID="", PROMPTPAY_ACCOUNT_NAME="")
    def test_wrong_amount_goes_to_review_and_admin_can_approve_and_reject(self):
        order = order_service.get_or_create_pending_order(user=self.student, course=self.course, package=pick_package(self.course, None))
        with mock.patch.object(slip_verification_service, "verify_slip_image", return_value=SlipData("AUTO2", Decimal("499"), [], [], {})):
            slip = self._slip(order)
            self.assertEqual(slip_verification_service.verify_slip(slip.pk), "manual_review")
        self.assertFalse(Enrollment.objects.exists())
        self.client.force_login(self.admin)
        r = self.client.post(reverse("dashboard:slip_decide", args=[slip.pk]), {"action": "approve"}, content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(Enrollment.objects.count(), 1)
        order2 = Order.objects.create(user=self.student, course=self.course, amount=500)
        slip2 = self._slip(order2)
        r = self.client.post(reverse("dashboard:slip_decide", args=[slip2.pk]), {"action": "reject", "reason": "ไม่ชัด"}, content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content[:300])
        slip2.refresh_from_db()
        self.assertEqual(slip2.status, "rejected")


class AccountAdminTests(DashCase):
    def test_cannot_disable_self_or_last_admin(self):
        with self.assertRaises(ActionError):
            account_service.set_active(self.admin, self.req, active=False)
        other = User.objects.create_user("b@x.com", "pw-12345678", full_name="B", phone="0844444444", is_staff=True)
        self.req.user = other
        account_service.set_active(self.admin, self.req, active=False)  # มีแอดมินอีกคน ปิดได้
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_active)
        self.req.user = self.admin
        with self.assertRaises(ActionError):
            account_service.set_active(other, self.req, active=False)  # ตัวเอง/คนสุดท้าย

    def test_disabled_student_cannot_login(self):
        account_service.set_active(self.student, self.req, active=False)
        self.assertFalse(self.client.login(username="s@x.com", password="pw-12345678"))


class SettingsTests(DashCase):
    @override_settings(PROMPTPAY_ID="0812345678")
    def test_site_setting_overrides_env_and_validates(self):
        self.assertEqual(settings_service.get("PROMPTPAY_ID"), "0812345678")
        self.client.force_login(self.admin)
        data = {"PROMPTPAY_ID": "0899999999", "PROMPTPAY_ACCOUNT_NAME": "", "LINE_CONTACT_URL": "", "EXPIRY_REMINDER_DAYS": "7,3,1", "ANNOUNCEMENT": "ปิดปรับปรุงคืนนี้"}
        r = self.client.post(reverse("dashboard:site_settings"), data)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(settings_service.get("PROMPTPAY_ID"), "0899999999")
        self.assertContains(self.client.get(reverse("core:home")), "ปิดปรับปรุงคืนนี้")
        bad = self.client.post(reverse("dashboard:site_settings"), {**data, "PROMPTPAY_ID": "123"})
        self.assertEqual(bad.status_code, 200)
        self.assertEqual(settings_service.get("PROMPTPAY_ID"), "0899999999")
        self.assertTrue(SiteSetting.objects.filter(key="ANNOUNCEMENT").exists())


class ListQueryCountTests(DashCase):
    def _count(self, url):
        with CaptureQueriesContext(connection) as ctx:
            self.assertEqual(self.client.get(url).status_code, 200)
        return len(ctx)

    def test_list_pages_do_not_n_plus_one(self):
        self.client.force_login(self.admin)
        urls = [reverse("dashboard:student_list"), reverse("dashboard:enrollment_list"), reverse("dashboard:order_list"),
                reverse("dashboard:course_list")]
        self._count(urls[0])  # อุ่นแคช (session/ContentType)
        def grow(start, n):
            for i in range(start, start + n):
                u = User.objects.create_user(f"n{i}@x.com", "pw-12345678", full_name=f"N{i}", phone=f"09{i:08d}")
                c = Course.objects.create(category=self.course.category, title=f"X{i}", slug=f"x{i}", price=1, is_published=True)
                Section.objects.create(course=c, title="s", order=1)
                enrollment_service.grant_or_extend(user=u, course=c)
                Order.objects.create(user=u, course=c, amount=1)

        grow(0, 3)
        few = [self._count(u) for u in urls]
        grow(3, 12)
        many = [self._count(u) for u in urls]
        self.assertEqual(few, many)  # จำนวน query ไม่โตตามจำนวนแถว


class PromoPriceTests(DashCase):
    """โปรเปิดตัว 1,490 → 990 หมดเขตตามวันที่ตั้ง แล้วกลับเป็นราคาปกติเอง"""

    def _promo(self, days_from_today, promo=990):
        from datetime import timedelta

        Course.objects.filter(pk=self.course.pk).update(
            price=1490, promo_price=promo, promo_ends_on=timezone.localdate() + timedelta(days=days_from_today)
        )
        return Course.objects.get(pk=self.course.pk)

    def test_active_until_end_of_last_day_then_reverts(self):
        self.assertEqual(self._promo(0).current_price, Decimal("990"))  # วันสุดท้ายยังใช้ราคาโปร
        c = self._promo(-1)
        self.assertFalse(c.promo_active)
        self.assertEqual(c.current_price, Decimal("1490"))

    def test_public_pages_and_checkout_use_promo_price(self):
        self._promo(30)
        r = self.client.get(reverse("courses:detail", args=["c"]))
        self.assertContains(r, "990")
        self.assertContains(r, "โปรเปิดตัว")
        self.assertContains(self.client.get(reverse("courses:list")), "990")
        self.client.force_login(self.student)
        self.client.get(reverse("payments:checkout", args=["c"]))
        self.assertEqual(Order.objects.get().amount, Decimal("990"))

    def test_pending_order_is_repriced_after_promo_ends(self):
        self._promo(0)
        course = Course.objects.prefetch_related("packages").get(pk=self.course.pk)
        order = order_service.get_or_create_pending_order(user=self.student, course=course, package=pick_package(course, None))
        self.assertEqual(order.amount, Decimal("990"))
        course = self._promo(-1)
        course = Course.objects.prefetch_related("packages").get(pk=course.pk)
        order = order_service.get_or_create_pending_order(user=self.student, course=course, package=pick_package(course, None))
        self.assertEqual(order.amount, Decimal("1490"))
        self.assertEqual(Order.objects.count(), 1)

    def test_paid_order_keeps_price_paid_even_after_promo_ends(self):
        course = Course.objects.prefetch_related("packages").get(pk=self._promo(5).pk)
        order = order_service.get_or_create_pending_order(user=self.student, course=course, package=pick_package(course, None))
        self._promo(-10)
        order_service.mark_paid(order_id=order.pk)
        order.refresh_from_db()
        self.assertEqual(order.amount, Decimal("990"))

    def test_form_validation(self):
        from apps.courses.forms import CourseForm

        base = {"category": self.course.category_id, "title": "X", "slug": "x", "price": "1490", "access_days": "365"}

        def errors(**extra):
            f = CourseForm({**base, **extra})
            f.is_valid()
            return f.errors

        self.assertIn("promo_ends_on", errors(promo_price="990"))  # ต้องมีวันสิ้นสุด
        self.assertIn("promo_price", errors(promo_price="1490", promo_ends_on="2030-01-01"))  # ต้องต่ำกว่าปกติ
        self.assertIn("promo_price", errors(promo_ends_on="2030-01-01"))  # มีวันแต่ไม่มีราคา
        self.assertIn("book_url", errors(book_url="http://shopee.co.th/x"))  # ต้อง https
        self.assertFalse(errors(promo_price="990", promo_ends_on="2030-01-01", book_url="https://shopee.co.th/x"))

    def test_chatbot_catalog_mentions_promo_and_default_is_365_days(self):
        from django.core.cache import cache

        from apps.chatbot.services import knowledge

        self._promo(10)
        cache.clear()
        text = knowledge.catalog_text()
        self.assertIn("990", text)
        self.assertIn("โปรโมชันถึง", text)
        self.assertEqual(Course._meta.get_field("access_days").default, 365)


@override_settings(LINE_CONTACT_URL="")  # ทดสอบกรณียังไม่ได้ตั้งลิงก์ LINE (ค่าตั้งต้นมีลิงก์แบรนด์แล้ว)
class ShopeeAndContactLinkTests(DashCase):
    def test_book_and_line_buttons_only_when_set(self):
        url = reverse("courses:detail", args=["c"])
        page = self.client.get(url).content.decode()
        self.assertNotIn("Shopee", page)
        self.assertNotIn("สอบถามทาง LINE ก่อนสมัคร", page)
        Course.objects.filter(pk=self.course.pk).update(book_url="https://shopee.co.th/product/1/2")
        SiteSetting.objects.create(key="LINE_CONTACT_URL", value="https://line.me/ti/p/abc")
        cache.clear()
        page = self.client.get(url).content.decode()
        self.assertIn("https://shopee.co.th/product/1/2", page)
        self.assertIn("https://line.me/ti/p/abc", page)
        self.assertIn("สอบถามทาง LINE ก่อนสมัคร", page)


class TelegramNotifyTests(DashCase):
    @override_settings(TELEGRAM_BOT_TOKEN="123:SECRET", TELEGRAM_CHAT_IDS=["1", "2"])
    def test_push_sends_to_every_chat_and_errors_do_not_leak_token(self):
        from apps.notifications.services import telegram_service

        ok = mock.Mock(status_code=200)
        with mock.patch.object(telegram_service.requests, "post", return_value=ok) as post:
            self.assertEqual(telegram_service.push_to_admins("hi"), 2)
        self.assertEqual([c.kwargs["json"]["chat_id"] for c in post.call_args_list], ["1", "2"])
        self.assertIn("bot123:SECRET", post.call_args.args[0])  # token อยู่ใน URL เท่านั้น
        import requests as rq

        with mock.patch.object(telegram_service.requests, "post", side_effect=rq.ConnectionError("https://api.telegram.org/bot123:SECRET/x")):
            with self.assertRaises(telegram_service.TelegramError) as cm:
                telegram_service.push_to_admins("hi")
        self.assertNotIn("SECRET", str(cm.exception))
        # chat id ผิด (400) ไม่ throw — ข้ามไป
        with mock.patch.object(telegram_service.requests, "post", return_value=mock.Mock(status_code=400, text="bad")):
            self.assertEqual(telegram_service.push_to_admins("hi"), 0)

    @override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_CHAT_IDS=[])
    def test_noop_when_not_configured(self):
        from apps.notifications.services import telegram_service

        with mock.patch.object(telegram_service.requests, "post") as post:
            self.assertEqual(telegram_service.push_to_admins("hi"), 0)
        post.assert_not_called()

    def test_signup_and_slip_and_paid_events_notify(self):
        with mock.patch("apps.notifications.tasks.notify_admins.delay") as notify, self.captureOnCommitCallbacks(execute=True):
            account_service.register_student(full_name="ใหม่", phone="0855555555", email="new@x.com", password="pw-12345678")
        self.assertIn("[สมัครใหม่]", notify.call_args.args[0])
        order = Order.objects.create(user=self.student, course=self.course, amount=500)
        with mock.patch("apps.notifications.tasks.notify_slip_submitted") as notify, \
                mock.patch("apps.payments.services.slip_verification_service.verify_slip", return_value="manual_review"), \
                self.captureOnCommitCallbacks(execute=True):
            slip = order_service.submit_slip(order=order, image=SimpleUploadedFile("s.png", PNG, "image/png"))
        notify.delay.assert_called_once_with(slip.pk)  # ตรวจเสร็จแล้วส่งรูปสลิป + ผลตรวจ (ดู apps/payments/tests.py)
        with mock.patch("apps.notifications.tasks.notify_admins.delay") as notify, self.captureOnCommitCallbacks(execute=True):
            order_service.mark_paid(order_id=order.pk)
        self.assertIn("[ชำระแล้ว]", notify.call_args.args[0])

    def test_default_reminders_for_one_year_course(self):
        self.assertEqual(settings_service.reminder_days(), [30, 7, 1])


class CodingRulesTests(DashCase):
    """กฎโค้ด: bulk แทนการ query ในลูป, logic อยู่ใน service, งานช้าเข้า Celery, ปิด django-admin ใน production"""

    def _add_sections(self, n):
        for i in range(n):
            sec = Section.objects.create(course=self.course, title=f"X{i}", order=10 + i)
            Lesson.objects.bulk_create(Lesson(section=sec, title=f"L{j}", youtube_video_id="M7lc1UVf-VE", order=j) for j in range(3))

    def _dup_queries(self):
        from apps.courses.services import catalog_service

        with CaptureQueriesContext(connection) as ctx:
            new = catalog_service.duplicate_course(self.course, self.req)
        return new, len(ctx.captured_queries)

    def test_duplicate_course_query_count_does_not_grow_with_sections(self):
        self._add_sections(1)
        new1, q1 = self._dup_queries()
        Course.all_objects.filter(pk=new1.pk).update(slug="other")  # ให้รอบสองไม่ต้องวนหา slug ใหม่ (เทียบแค่ผลของจำนวนบท)
        self._add_sections(4)
        new2, q2 = self._dup_queries()
        self.assertEqual(q1, q2)
        self.assertEqual(Lesson.objects.filter(section__course=new2).count(), Lesson.objects.filter(section__course=self.course).count())
        self.assertEqual(list(new2.sections.order_by("order").values_list("title", flat=True)),
                         list(self.course.sections.order_by("order").values_list("title", flat=True)))

    def test_move_section_reorders_with_single_update(self):
        from apps.courses.services import catalog_service

        self._add_sections(3)
        last = self.course.sections.order_by("-order").first()
        catalog_service.move_section(last, "up")
        titles = list(self.course.sections.order_by("order").values_list("title", flat=True))
        self.assertEqual(titles, ["S", "X0", "X2", "X1"])
        self.assertEqual(list(self.course.sections.order_by("order").values_list("order", flat=True)), [1, 2, 3, 4])

    def test_settings_save_many_upserts(self):
        settings_service.save_many({"ANNOUNCEMENT": "a"})
        settings_service.save_many({"ANNOUNCEMENT": "b", "LINE_CONTACT_URL": "https://line.me/ti/p/x"})
        self.assertEqual(SiteSetting.objects.get(key="ANNOUNCEMENT").value, "b")
        self.assertEqual(SiteSetting.objects.filter(key="ANNOUNCEMENT").count(), 1)

    def test_bulk_remind_counts_only_existing_and_queues_celery(self):
        enr = enrollment_service.grant_or_extend(user=self.student, course=self.course)
        self.client.force_login(self.admin)
        with mock.patch("apps.notifications.services.reminder_service.send_expiry_email.delay") as delay:
            r = self.client.post(reverse("dashboard:enrollment_bulk"), {"action": "remind", "ids": [enr.pk, 999999]},
                                 content_type="application/json", HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(r.json()["message"], "ส่งอีเมลเตือน 1 รายการแล้ว")
        delay.assert_called_once()

    def test_export_request_queues_task_after_commit(self):
        self.client.force_login(self.admin)
        with mock.patch("apps.dashboard.services.export_service.generate_report_task.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post(reverse("dashboard:exports"), {"kind": "sales", "fmt": "xlsx"})
        delay.assert_called_once()
        self.assertTrue(AuditLog.objects.filter(action="export").exists())

    def test_django_admin_disabled_unless_flag(self):
        import importlib

        from django.urls import clear_url_caches

        import config.urls

        try:
            with override_settings(DJANGO_ADMIN_ENABLED=False):
                clear_url_caches(); importlib.reload(config.urls)
                self.assertFalse(any(str(p.pattern) == "django-admin/" for p in config.urls.urlpatterns))
        finally:
            clear_url_caches(); importlib.reload(config.urls)
        self.assertTrue(any(str(p.pattern) == "django-admin/" for p in config.urls.urlpatterns))  # ตอนพัฒนาเปิดไว้


class PaymentQueueTests(DashCase):
    """หน้า "การชำระเงิน": ออเดอร์ + สลิปล่าสุดในแถวเดียว แท็บตามงาน แผงรายละเอียด"""

    def _review_order(self, amount=500):
        order = Order.objects.create(user=self.student, course=self.course, amount=amount, status=Order.Status.REVIEWING)
        slip = PaymentSlip.objects.create(order=order, image=SimpleUploadedFile("s.png", PNG, "image/png"),
                                          status=PaymentSlip.Status.MANUAL_REVIEW, reason="ยอดไม่ตรง", verified_amount=Decimal("499"))
        return order, slip

    def test_review_tab_is_default_and_shows_slip_with_inline_actions(self):
        order, slip = self._review_order()
        Order.objects.create(user=self.student, course=self.course, amount=500, status=Order.Status.PAID)
        self.client.force_login(self.admin)
        r = self.client.get(reverse("dashboard:order_list"))
        self.assertEqual(r.context["tab"], "review")
        self.assertEqual(len(r.context["ls"].page.object_list), 1)
        self.assertContains(r, reverse("payments:slip_image", args=[slip.pk]))
        self.assertContains(r, reverse("dashboard:slip_decide", args=[slip.pk]))
        self.assertContains(r, "สลิป ฿499")
        self.assertEqual(dict((k, n) for k, _, n in r.context["tabs"])["paid"], 1)

    def test_without_pending_work_defaults_to_all(self):
        Order.objects.create(user=self.student, course=self.course, amount=500, status=Order.Status.PAID)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("dashboard:order_list")).context["tab"], "all")

    def test_detail_opens_as_panel_for_fetch(self):
        order, slip = self._review_order()
        self.client.force_login(self.admin)
        url = reverse("dashboard:order_detail", args=[order.pk])
        r = self.client.get(url, HTTP_X_REQUESTED_WITH="fetch")
        self.assertTemplateUsed(r, "dashboard/_payment_panel.html")
        self.assertNotContains(r, "<html")
        self.assertTemplateUsed(self.client.get(url), "dashboard/order_detail.html")


class StudentManageTests(DashCase):
    """หน้าต่างนักเรียน: ข้อมูลส่วนตัว + สิทธิ์ทุกคอร์ส บันทึกครั้งเดียว"""

    def setUp(self):
        super().setUp()
        self.other = Course.objects.create(category=self.course.category, title="Other", slug="other", price=1, access_days=30, is_published=True)
        self.url = reverse("dashboard:student_manage", args=[self.student.pk])
        self.client.force_login(self.admin)

    def _post(self, **extra):
        data = {"full_name": "Stu", "phone": "0811111111", "email": "s@x.com", "admin_note": ""}
        data.update(extra)
        return self.client.post(self.url, data, HTTP_X_REQUESTED_WITH="fetch")

    def test_lists_every_course(self):
        r = self.client.get(self.url, HTTP_X_REQUESTED_WITH="fetch")
        self.assertContains(r, f'name="on-{self.course.pk}"')
        self.assertContains(r, f'name="on-{self.other.pk}"')

    def test_grant_set_date_and_revoke_in_one_save(self):
        enrollment_service.grant_or_extend(user=self.student, course=self.course)
        r = self._post(**{f"on-{self.other.pk}": "on", f"exp-{self.other.pk}": "2030-01-31", "full_name": "Stu New"})
        self.assertEqual(r.json()["ok"], True, r.content[:300])
        self.assertIn("2 คอร์ส", r.json()["message"])
        self.student.refresh_from_db()
        self.assertEqual(self.student.full_name, "Stu New")
        self.assertEqual(Enrollment.objects.get(user=self.student, course=self.course).status, "cancelled")
        e = Enrollment.objects.get(user=self.student, course=self.other)
        self.assertEqual((e.status, timezone.localtime(e.expires_at).date().isoformat(), e.source), ("active", "2030-01-31", "manual"))
        self.assertEqual(AuditLog.objects.filter(action__in=["grant", "revoke"]).count(), 2)

    def test_turning_on_without_date_uses_course_length_and_unchanged_rows_are_untouched(self):
        enrollment_service.grant_or_extend(user=self.student, course=self.course)
        exp = timezone.localtime(Enrollment.objects.get(course=self.course).expires_at).date().isoformat()
        r = self._post(**{f"on-{self.course.pk}": "on", f"exp-{self.course.pk}": exp, f"on-{self.other.pk}": "on"})
        self.assertEqual(r.json()["message"], "บันทึกแล้ว · เปลี่ยนสิทธิ์เรียน 1 คอร์ส")
        e = Enrollment.objects.get(course=self.other)
        self.assertEqual((e.expires_at - timezone.now()).days, 29)

    def test_invalid_profile_shows_errors_and_changes_nothing(self):
        User.objects.create_user("taken@x.com", "pw-12345678", full_name="T", phone="0822222222")
        r = self._post(email="taken@x.com", **{f"on-{self.other.pk}": "on"})
        self.assertEqual(r.status_code, 422)
        self.assertFalse(Enrollment.objects.filter(course=self.other).exists())


class CourseContentDragTests(DashCase):
    """เนื้อหาคอร์ส: ลากวางจัดลำดับ, เรียงตามเลขในชื่อ, แนบ PDF ในฟอร์มคลิป"""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.sec = self.lesson.section
        self.l10 = Lesson.objects.create(section=self.sec, title="คลิปที่ 10", youtube_video_id="M7lc1UVf-VE", order=2)
        self.l2 = Lesson.objects.create(section=self.sec, title="คลิปที่ 2", youtube_video_id="M7lc1UVf-VE", order=3)
        self.url = reverse("dashboard:course_reorder", args=[self.course.pk])

    def _order(self):
        return list(Lesson.objects.filter(section=self.sec).order_by("order").values_list("pk", flat=True))

    def test_drag_reorder_lessons(self):
        ids = [self.l2.pk, self.lesson.pk, self.l10.pk]
        r = self.client.post(self.url, {"kind": "lessons", "parent": self.sec.pk, "ids": ids}, content_type="application/json")
        self.assertEqual(r.json()["ok"], True)
        self.assertEqual(self._order(), ids)

    def test_reorder_rejects_ids_from_elsewhere(self):
        r = self.client.post(self.url, {"kind": "lessons", "parent": self.sec.pk, "ids": [self.l2.pk, self.lesson.pk]}, content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_reorder_sections(self):
        s2 = Section.objects.create(course=self.course, title="S2", order=2)
        r = self.client.post(self.url, {"kind": "sections", "ids": [s2.pk, self.sec.pk]}, content_type="application/json")
        self.assertEqual(r.json()["ok"], True)
        self.assertEqual(list(Section.objects.filter(course=self.course).order_by("order").values_list("pk", flat=True)), [s2.pk, self.sec.pk])

    def test_sort_by_number_in_title(self):
        self.client.post(reverse("dashboard:section_sort", args=[self.sec.pk]))
        self.assertEqual(self._order(), [self.l2.pk, self.l10.pk, self.lesson.pk])  # "L" ไม่มีเลข → ท้ายสุด

    def test_lesson_form_can_attach_pdf(self):
        pdf = SimpleUploadedFile("worksheet.pdf", b"%PDF-1.4 test", "application/pdf")
        r = self.client.post(reverse("dashboard:lesson_edit", args=[self.l2.pk]), {
            "title": "คลิปที่ 2", "youtube_url": "M7lc1UVf-VE", "duration_seconds": 0, "order": 3, "pdf_file": pdf, "pdf_title": "แบบฝึกหัด",
        }, HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(r.json()["ok"], True, r.content[:300])
        self.assertEqual(list(self.l2.attachments.values_list("title", flat=True)), ["แบบฝึกหัด"])


class BroadcastTests(DashCase):
    def test_targets_and_send_personalised_emails(self):
        from django.core import mail

        enrollment_service.grant_or_extend(user=self.student, course=self.course)
        User.objects.create_user("idle@x.com", "pw-12345678", full_name="Idle", phone="0833333333")
        self.client.force_login(self.admin)
        r = self.client.get(reverse("dashboard:broadcast"))
        self.assertContains(r, "กำลังเรียนอยู่ (ทุกคอร์ส) — 1 คน")
        self.assertContains(r, "บัญชีนักเรียนทั้งหมด — 2 คน")
        r = self.client.post(reverse("dashboard:broadcast"), {"target": "active", "subject": "คลิปใหม่", "message": "มีคลิปใหม่แล้ว", "do": "send"})
        self.assertRedirects(r, reverse("dashboard:broadcast"))
        self.assertEqual([m.to for m in mail.outbox], [["s@x.com"]])
        self.assertIn("สวัสดีค่ะ คุณStu", mail.outbox[0].body)
        self.assertEqual(AuditLog.objects.get(action="broadcast").changes["recipients"], 1)

    def test_test_send_goes_only_to_admin(self):
        from django.core import mail

        self.client.force_login(self.admin)
        self.client.post(reverse("dashboard:broadcast"), {"target": "all", "subject": "ลอง", "message": "x", "do": "test"})
        self.assertEqual([m.to for m in mail.outbox], [["a@x.com"]])
        self.assertTrue(mail.outbox[0].subject.startswith("[ทดสอบ]"))


class StudentImportTests(DashCase):
    def _upload(self, text, encoding="utf-8-sig", **extra):
        f = SimpleUploadedFile("students.csv", text.encode(encoding), "text/csv")
        self.client.force_login(self.admin)
        data = {"file": f}
        data.update(extra)
        return self.client.post(reverse("dashboard:student_import"), data)

    def test_import_creates_accounts_grants_course_and_reports_bad_rows(self):
        from django.core import mail

        csv_text = (
            "ชื่อ-นามสกุล,อีเมล,เบอร์โทร,วันหมดอายุ\n"
            "เด็กหนึ่ง,One@x.com,812345678,31/12/2570\n"      # เบอร์โดน Excel ตัด 0 + ปี พ.ศ.
            "นักเรียนเดิม,s@x.com,0811111111,\n"               # มีบัญชีอยู่แล้ว
            ",nobody@x.com,0811111112,\n"                       # ไม่มีชื่อ
            "ซ้ำ,one@x.com,0811111113,\n"                       # อีเมลซ้ำในไฟล์
            "เบอร์ผิด,bad@x.com,12,\n"
        )
        r = self._upload(csv_text, course=self.course.pk, send_email="on")
        res = r.context["result"]
        self.assertEqual((res["created"], res["existing"], res["granted"], len(res["errors"])), (1, 1, 2, 3))
        u = User.objects.get(email="one@x.com")
        self.assertEqual(u.phone, "0812345678")
        self.assertFalse(u.has_usable_password())
        e = Enrollment.objects.get(user=u)
        self.assertEqual(timezone.localtime(e.expires_at).date().isoformat(), "2027-12-31")
        self.assertTrue(Enrollment.objects.filter(user=self.student, course=self.course, status="active").exists())
        self.assertEqual([m.to for m in mail.outbox], [["one@x.com"]])  # ส่งลิงก์เฉพาะบัญชีใหม่
        self.assertIn("/accounts/password/reset/", mail.outbox[0].body)

    def test_thai_excel_cp874_file_and_missing_columns(self):
        r = self._upload("ชื่อ,อีเมล,เบอร์\nทดสอบ,cp@x.com,0899999999\n", encoding="cp874")
        self.assertEqual(r.context["result"]["created"], 1)
        r = self._upload("name,phone\nA,0811111111\n")
        self.assertIn("ไม่พบคอลัมน์", str(r.context["form"].errors))

    def test_template_download(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse("dashboard:student_import_template"))
        self.assertIn("อีเมล", r.content.decode("utf-8-sig"))


class PasswordResetTests(DashCase):
    def test_imported_user_without_password_can_set_one(self):
        from django.core import mail

        u = User.objects.create_user("new@x.com", None, full_name="New", phone="0844444444")
        self.client.post(reverse("accounts:password_reset"), {"email": "new@x.com"})
        self.assertEqual(len(mail.outbox), 1)
        link = next(line for line in mail.outbox[0].body.splitlines() if "/accounts/password/reset/" in line)
        path = link[link.index("/accounts/"):]
        r = self.client.get(path, follow=True)  # Django เปลี่ยนเป็น URL set-password ก่อน
        r = self.client.post(r.redirect_chain[-1][0], {"new_password1": "Sup3r-secret-99", "new_password2": "Sup3r-secret-99"})
        self.assertRedirects(r, reverse("accounts:password_reset_complete"))
        u.refresh_from_db()
        self.assertTrue(u.check_password("Sup3r-secret-99"))

    def test_unknown_email_gives_same_page(self):
        r = self.client.post(reverse("accounts:password_reset"), {"email": "nobody@x.com"})
        self.assertRedirects(r, reverse("accounts:password_reset_done"))


class LessonDurationAutoTests(DashCase):
    """แอดมินไม่ต้องกรอกความยาวคลิป — ระบบเก็บจาก YouTube player ตอนมีคนดูครั้งแรก"""

    def test_lesson_form_has_no_duration_and_saves(self):
        self.client.force_login(self.admin)
        url = reverse("dashboard:lesson_add", args=[self.lesson.section_id])
        self.assertNotContains(self.client.get(url, HTTP_X_REQUESTED_WITH="fetch"), 'name="duration_seconds"')
        r = self.client.post(url, {"title": "ใหม่", "youtube_url": "https://youtu.be/M7lc1UVf-VE", "order": 5}, HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(r.json()["ok"], True, r.content[:300])
        self.assertEqual(Lesson.objects.get(title="ใหม่").duration_seconds, 0)

    def test_first_progress_report_fills_duration_once(self):
        from apps.learning.services import progress_service

        Lesson.objects.filter(pk=self.lesson.pk).update(duration_seconds=0)
        lesson = Lesson.objects.get(pk=self.lesson.pk)
        progress_service.save_progress(user=self.student, lesson=lesson, position=10, watched_delta=10, client_duration=1342)
        self.assertEqual(Lesson.objects.get(pk=lesson.pk).duration_seconds, 1342)
        progress_service.save_progress(user=self.student, lesson=Lesson.objects.get(pk=lesson.pk), position=20, watched_delta=10, client_duration=99999)
        self.assertEqual(Lesson.objects.get(pk=lesson.pk).duration_seconds, 1342)  # ไม่ถูกทับ / ค่าแปลกไม่รับ

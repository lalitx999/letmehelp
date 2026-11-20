"""EasySlip V2 client + การเทียบผู้รับเงิน + แจ้งเตือน Telegram พร้อมรูปสลิป"""
from decimal import Decimal
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from apps.core.tests import PNG, BaseCase
from apps.courses.services.pricing_service import pick_package
from apps.notifications import tasks as notify_tasks
from apps.payments.models import PaymentSlip
from apps.payments.services import easyslip_client, order_service, slip_verification_service
from apps.payments.services.easyslip_client import EasySlipError, SlipData, SlipNotFound

V2_OK = {
    "success": True,
    "message": "Bank slip verified successfully",
    "data": {
        "isDuplicate": False,
        "amountInOrder": 990,
        "amountInSlip": 990,
        "isAmountMatched": True,
        "matchedAccount": None,
        "rawSlip": {
            "transRef": "016310103318AOR05577",
            "date": "2026-11-06T10:33:00+07:00",
            "amount": {"amount": 990, "local": {"amount": 990, "currency": "THB"}},
            "sender": {
                "bank": {"id": "004", "name": "กสิกรไทย", "short": "KBANK"},
                "account": {"name": {"th": "น.ส. ธัชพรรณ ก"}, "bank": {"type": "BANKAC", "account": "xxx-x-x9968-x"}},
            },
            "receiver": {
                "bank": {"id": "014", "name": "ไทยพาณิชย์", "short": "SCB"},
                "account": {
                    "name": {"th": "น.ส. ศิตา ว", "en": "MISS SITA W"},
                    "bank": {"type": "BANKAC", "account": "xxx-x-x8459-x"},
                    "proxy": {"type": "MSISDN", "account": "xxx-xxx-6499"},
                },
            },
        },
    },
}


def _resp(status, body):
    r = mock.Mock(status_code=status)
    r.json.return_value = body
    return r


@override_settings(EASYSLIP_API_KEY="k", EASYSLIP_API_URL="https://api.easyslip.com/v2/verify/bank")
class EasySlipV2ClientTests(SimpleTestCase):
    def test_parses_v2_success_and_sends_v2_fields(self):
        with mock.patch.object(easyslip_client.requests, "post", return_value=_resp(200, V2_OK)) as post:
            data = easyslip_client.verify_slip_image(b"img", expected_amount=Decimal("990"), remark="order-7")
        kwargs = post.call_args.kwargs
        self.assertIn("image", kwargs["files"])  # V2 ใช้ชื่อฟิลด์ image (V1 ใช้ file)
        self.assertEqual(kwargs["data"], {"checkDuplicate": "true", "matchAmount": "990.00", "remark": "order-7"})
        self.assertEqual(data.trans_ref, "016310103318AOR05577")
        self.assertEqual(data.amount, Decimal("990"))
        self.assertIn("น.ส. ศิตา ว", data.receiver_names)
        self.assertEqual(data.receiver_masked_ids, ["xxx-x-x8459-x", "xxx-xxx-6499"])
        self.assertFalse(data.is_duplicate)
        self.assertEqual(data.sender_bank, "KBANK")

    def test_unreadable_slip_raises_slip_not_found(self):
        body = {"success": False, "error": {"code": "SLIP_NOT_FOUND", "message": "No QR code found in the image"}}
        with mock.patch.object(easyslip_client.requests, "post", return_value=_resp(404, body)):
            with self.assertRaises(SlipNotFound):
                easyslip_client.verify_slip_image(b"img")

    def test_quota_and_pending_are_retryable(self):
        for status, code in ((403, "QUOTA_EXCEEDED"), (404, "SLIP_PENDING"), (401, "INVALID_API_KEY"), (500, "API_SERVER_ERROR")):
            body = {"success": False, "error": {"code": code, "message": "x"}}
            with mock.patch.object(easyslip_client.requests, "post", return_value=_resp(status, body)):
                with self.assertRaises(EasySlipError, msg=code):
                    easyslip_client.verify_slip_image(b"img")


@override_settings(PROMPTPAY_ID="0939546499", PROMPTPAY_BANK_ACCOUNT="419-008459-4", PROMPTPAY_ACCOUNT_NAME="ศิตา วาริชวิวัฒน์")
class ReceiverMatchTests(BaseCase):
    def _data(self, names=(), ids=()):
        return SlipData("R", Decimal("1"), list(names), list(ids), {})

    def test_matches_bank_account_promptpay_and_short_name(self):
        ok = slip_verification_service._receiver_ok
        self.assertTrue(ok(self._data(ids=["xxx-x-x8459-x"])))
        self.assertTrue(ok(self._data(ids=["xxx-xxx-6499"])))
        self.assertTrue(ok(self._data(names=["น.ส. ศิตา ว"])))
        self.assertTrue(ok(self._data(names=["นางสาว ศิตา วาริชวิวัฒน์"])))

    def test_rejects_other_people(self):
        ok = slip_verification_service._receiver_ok
        self.assertFalse(ok(self._data(names=["บจก. ออโต้บอทยูเอ"], ids=["xxx-x-x6925-x"])))
        self.assertFalse(ok(self._data(ids=["xxx-xxx-1234"])))
        self.assertFalse(ok(self._data(names=["น.ส. ศิ"])))  # สั้นเกินจะเชื่อได้


class SlipFlowV2Tests(BaseCase):
    def _slip(self, order):
        return PaymentSlip.objects.create(order=order, image=SimpleUploadedFile("s.png", PNG, "image/png"))

    @override_settings(EASYSLIP_API_KEY="k", PROMPTPAY_ID="0939546499", PROMPTPAY_BANK_ACCOUNT="", PROMPTPAY_ACCOUNT_NAME="")
    def test_easyslip_duplicate_unknown_to_us_goes_to_manual_review(self):
        order = order_service.get_or_create_pending_order(user=self.user, course=self.course, package=pick_package(self.course, None))
        data = SlipData("DUP1", order.amount, [], ["xxx-xxx-6499"], {}, is_duplicate=True)
        with mock.patch.object(slip_verification_service, "verify_slip_image", return_value=data):
            slip = self._slip(order)
            self.assertEqual(slip_verification_service.verify_slip(slip.pk), "manual_review")
        slip.refresh_from_db()
        self.assertIn("เคยถูกตรวจ", slip.reason)

    @override_settings(TELEGRAM_BOT_TOKEN="t", TELEGRAM_CHAT_IDS=["-100"], SITE_URL="https://letmehelp.example")
    def test_slip_notification_sends_photo_with_order_details(self):
        order = order_service.get_or_create_pending_order(user=self.user, course=self.course, package=pick_package(self.course, None))
        slip = self._slip(order)
        with mock.patch.object(notify_tasks.telegram_service, "send_photo", return_value=True) as send_photo:
            self.assertEqual(notify_tasks.notify_slip_submitted(slip.pk), 1)
        chat_id, photo, caption, _ = send_photo.call_args.args
        self.assertEqual(chat_id, "-100")
        self.assertEqual(photo, PNG)
        for part in (f"#{order.pk}", self.user.email, self.user.phone, self.course.title, "https://letmehelp.example/dashboard/slips/"):
            self.assertIn(part, caption)
        self.assertIn("กำลังตรวจ", caption)  # ยังไม่ตรวจ
        PaymentSlip.objects.filter(pk=slip.pk).update(status=PaymentSlip.Status.MANUAL_REVIEW, reason="ยอดไม่ตรง")
        with mock.patch.object(notify_tasks.telegram_service, "send_photo", return_value=True) as send_photo:
            notify_tasks.notify_slip_submitted(slip.pk)
        self.assertIn("⚠️ รอแอดมินตรวจ — ยอดไม่ตรง", send_photo.call_args.args[2])

    @override_settings(TELEGRAM_BOT_TOKEN="t", TELEGRAM_CHAT_IDS=["-100"])
    def test_falls_back_to_text_when_photo_fails(self):
        order = order_service.get_or_create_pending_order(user=self.user, course=self.course, package=pick_package(self.course, None))
        slip = self._slip(order)
        with mock.patch.object(notify_tasks.telegram_service, "send_photo", return_value=False), \
                mock.patch.object(notify_tasks.telegram_service, "send_text", return_value=True) as send_text:
            self.assertEqual(notify_tasks.notify_slip_submitted(slip.pk), 1)
        send_text.assert_called_once()


class PromptPayAndImageTests(SimpleTestCase):
    def test_qr_locks_amount_for_real_account(self):
        from apps.payments.services import promptpay

        p = promptpay.build_payload("093-954-6499", Decimal("990"))
        self.assertEqual(p, "00020101021229370016A0000006770101110113006693954649953037645406990.005802TH6304C62D")
        self.assertIn("010212", p)  # 12 = QR ระบุยอด

    def test_ewallet_and_invalid_ids(self):
        from apps.payments.services import promptpay

        self.assertIn("0315123456789012345", promptpay.build_payload("123456789012345", Decimal("1")))
        for bad in ("12345", "1234567890"):
            with self.assertRaises(ValueError):
                promptpay.build_payload(bad, Decimal("1"))
        with self.assertRaises(ValueError):
            promptpay.build_payload("0939546499", Decimal("0"))

    def test_large_slip_is_shrunk_under_4mb(self):
        import io
        import os

        from PIL import Image

        img = Image.frombytes("RGB", (3000, 3000), os.urandom(3000 * 3000 * 3))  # สุ่มพิกเซล = บีบอัดยาก
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        self.assertGreater(buf.tell(), easyslip_client.MAX_IMAGE_BYTES)
        buf.seek(0)
        out = easyslip_client._fit_image(buf)
        self.assertLessEqual(len(out), easyslip_client.MAX_IMAGE_BYTES)
        small = b"x" * 100
        self.assertEqual(easyslip_client._fit_image(io.BytesIO(small)), small)


class EmptyCourseTests(BaseCase):
    def test_paid_student_sees_empty_course_page_not_404(self):
        from django.urls import reverse

        from apps.courses.models import Section
        from apps.enrollments.services import enrollment_service

        Section.objects.filter(course=self.course).delete()  # คอร์สยังไม่มีบทเรียน
        enrollment_service.grant_or_extend(user=self.user, course=self.course, days=365)
        self.client.force_login(self.user)
        resp = self.client.get(reverse("learning:player", kwargs={"slug": self.course.slug}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "กำลังอัปโหลดบทเรียน")

    def test_unknown_course_uses_custom_404(self):
        resp = self.client.get("/learn/no-such-course/")
        self.assertEqual(resp.status_code, 404)
        self.assertContains(resp, "ไม่พบหน้าที่คุณต้องการ", status_code=404)

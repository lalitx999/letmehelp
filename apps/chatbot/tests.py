from types import SimpleNamespace
from unittest import mock

import anthropic
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.core.tests import make_course
from apps.courses.models import CoursePackage
from apps.enrollments.services import enrollment_service

from .services import chat_service, faq_bot, knowledge


def stub_response(text="ตอบจากโมเดล", stop_reason="end_turn"):
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)])


class ChatbotBase(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("s@x.com", "pw-12345678", full_name="S", phone="0811111111")
        self.course, self.lesson = make_course(price=1490, days=180)
        CoursePackage.objects.create(course=self.course, label="1 ปี", days=365, price=2384)

    def post(self, messages, **extra):
        return self.client.post(reverse("chatbot:chat"), {"messages": messages, **extra}, content_type="application/json")


class HistoryTests(TestCase):
    def test_clean_history(self):
        raw = [{"role": "assistant", "content": "ทัก"}, {"role": "user", "content": "x" * 5000}, "junk", {"role": "bot", "content": "ok"}, {"role": "user", "content": "  "}]
        out = chat_service.clean_history(raw)
        self.assertEqual(out[0]["role"], "user")          # ตัด assistant นำหน้า
        self.assertEqual(len(out[0]["content"]), chat_service.MAX_CHARS)
        self.assertEqual([m["role"] for m in out], ["user", "assistant"])  # 'bot' → assistant, ข้อความว่างถูกทิ้ง

    def test_history_is_capped(self):
        raw = [{"role": "user", "content": str(i)} for i in range(50)]
        self.assertEqual(len(chat_service.clean_history(raw)), chat_service.MAX_HISTORY)


class FaqBotTests(ChatbotBase):
    def test_price_answer_uses_database_prices(self):
        text, sugg = faq_bot.answer("ราคาเท่าไหร่")
        self.assertIn("1,490", text)
        self.assertIn("2,384", text)       # แพ็กเกจเสริมจากฐานข้อมูล
        self.assertIn("/courses/c/", text)
        self.assertTrue(sugg)

    def test_other_intents_and_fallback(self):
        self.assertIn("/free-trial/", faq_bot.answer("มีคลิปฟรีไหม")[0])
        self.assertIn("PromptPay", faq_bot.answer("โอนยังไง")[0])
        self.assertIn("ผู้ดูแล", faq_bot.answer("ขอคืนเงิน")[0])
        self.assertIn("ไม่แน่ใจ", faq_bot.answer("ฟหกดเ")[0])

    def test_catalog_hides_unpublished(self):
        self.course.is_published = False
        self.course.save()
        cache.clear()
        self.assertEqual(knowledge.catalog(), [])


class ChatViewTests(ChatbotBase):
    @override_settings(ANTHROPIC_API_KEY="")
    def test_works_without_api_key(self):
        r = self.post([{"role": "user", "content": "ราคา"}])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["source"], "faq")
        self.assertIn("1,490", r.json()["reply"])

    def test_bad_input(self):
        self.assertEqual(self.client.post(reverse("chatbot:chat"), "not json", content_type="application/json").status_code, 400)
        self.assertEqual(self.post([]).status_code, 400)
        self.assertEqual(self.post([{"role": "assistant", "content": "hi"}]).status_code, 400)
        self.assertEqual(self.client.get(reverse("chatbot:chat")).status_code, 405)

    @override_settings(ANTHROPIC_API_KEY="")
    def test_rate_limit(self):
        for _ in range(chat_service.RATE_LIMIT):
            self.assertEqual(self.post([{"role": "user", "content": "สวัสดี"}]).status_code, 200)
        r = self.post([{"role": "user", "content": "สวัสดี"}])
        self.assertEqual(r.status_code, 429)

    @override_settings(ANTHROPIC_API_KEY="k")
    def test_tutor_mode_requires_enrollment(self):
        client_cls = mock.MagicMock()
        client_cls.return_value.beta.messages.create.return_value = stub_response("อธิบาย tense")
        with mock.patch.object(chat_service.anthropic, "Anthropic", client_cls):
            self.client.force_login(self.user)
            self.post([{"role": "user", "content": "อธิบายหน่อย"}], lesson_id=self.lesson.pk)
            system_no_access = client_cls.return_value.beta.messages.create.call_args.kwargs["system"]
            self.assertNotIn("กำลังดู", system_no_access)  # ไม่มีสิทธิ์ → ตกเป็นโหมดทั่วไป ไม่เห็นข้อมูลบทเรียน
            enrollment_service.grant_or_extend(user=self.user, course=self.course)
            r = self.post([{"role": "user", "content": "อธิบายหน่อย"}], lesson_id=self.lesson.pk)
            system_ok = client_cls.return_value.beta.messages.create.call_args.kwargs["system"]
            self.assertIn("กำลังดู", system_ok)
            self.assertEqual(r.json()["mode"], "tutor")


@override_settings(ANTHROPIC_API_KEY="k", CHATBOT_MODEL="claude-opus-5-5", CHATBOT_EFFORT="low", CHATBOT_FALLBACK_MODEL="claude-opus-4-8")
class LlmPathTests(ChatbotBase):
    def run_reply(self, create_mock):
        client_cls = mock.MagicMock()
        client_cls.return_value.beta.messages.create = create_mock
        client_cls.return_value.messages.create = create_mock
        with mock.patch.object(chat_service.anthropic, "Anthropic", client_cls):
            return chat_service.reply(history=[{"role": "user", "content": "ราคา"}])

    def test_uses_claude_and_prompt_has_live_catalog(self):
        create = mock.MagicMock(return_value=stub_response("คอร์สนี้ 1,490 บาท"))
        r = self.run_reply(create)
        self.assertEqual((r.source, r.text), ("ai", "คอร์สนี้ 1,490 บาท"))
        kw = create.call_args.kwargs
        self.assertEqual(kw["model"], "claude-opus-5-5")
        self.assertEqual(kw["output_config"], {"effort": "low"})
        self.assertEqual(kw["fallbacks"], [{"model": "claude-opus-4-8"}])
        self.assertIn("1,490", kw["system"])                # ราคามาจากฐานข้อมูล
        self.assertNotIn("temperature", kw)                  # โมเดลรุ่นนี้ไม่รับ sampling params

    def test_refusal_falls_back_to_faq(self):
        r = self.run_reply(mock.MagicMock(return_value=stub_response(stop_reason="refusal")))
        self.assertEqual(r.source, "faq")

    def test_api_error_falls_back_to_faq(self):
        err = anthropic.APIConnectionError(request=mock.MagicMock())
        r = self.run_reply(mock.MagicMock(side_effect=err))
        self.assertEqual(r.source, "faq")
        self.assertIn("1,490", r.text)

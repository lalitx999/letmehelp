"""แชทบอท: เรียก Claude (Anthropic SDK) ถ้าตั้ง ANTHROPIC_API_KEY ไม่เช่นนั้น/เมื่อเรียกไม่สำเร็จ ใช้บอทกติกา (faq_bot)"""
import logging
from dataclasses import dataclass

import anthropic
from django.conf import settings
from django.core.cache import cache

from . import faq_bot, knowledge

logger = logging.getLogger(__name__)

MAX_HISTORY = 10          # ข้อความล่าสุดที่ส่งให้โมเดล
MAX_CHARS = 800           # ความยาวต่อข้อความ (กันค่าใช้จ่ายบวม/ส่งเอกสารยาวเข้ามา)
RATE_LIMIT = 20           # ข้อความ ต่อ ช่วงเวลา ต่อผู้ใช้/IP
RATE_WINDOW = 600         # วินาที


@dataclass
class Reply:
    text: str
    source: str  # "ai" | "faq"
    suggestions: list[str]


def clean_history(raw) -> list[dict]:
    """รับ [{role, content}] จาก client ที่เชื่อถือไม่ได้ → ประวัติที่ปลอดภัยและเริ่มด้วย user เสมอ"""
    out = []
    for m in (raw or [])[-MAX_HISTORY:]:
        if not isinstance(m, dict):
            continue
        role = "assistant" if m.get("role") in ("assistant", "bot") else "user"
        text = str(m.get("content", "")).strip()[:MAX_CHARS]
        if text:
            out.append({"role": role, "content": text})
    while out and out[0]["role"] != "user":
        out.pop(0)
    return out


def is_rate_limited(ident: str) -> bool:
    key = f"chatbot:rate:{ident}"
    if cache.add(key, 1, RATE_WINDOW):
        return False
    try:
        return cache.incr(key) > RATE_LIMIT
    except ValueError:  # key หมดอายุพอดี
        cache.set(key, 1, RATE_WINDOW)
        return False


def llm_enabled() -> bool:
    return bool(settings.ANTHROPIC_API_KEY)


def _call_claude(system: str, history: list[dict]) -> str:
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=30.0, max_retries=1)
    kwargs = dict(
        model=settings.CHATBOT_MODEL,
        max_tokens=1024,
        system=system,
        messages=history,
        # แชทตอบสั้น: ลดความลึกในการคิดเพื่อความเร็ว/ค่าใช้จ่าย (โมเดลรุ่นนี้ปิด thinking ไม่ได้ จึงคุมด้วย effort)
        output_config={"effort": settings.CHATBOT_EFFORT},
    )
    if settings.CHATBOT_FALLBACK_MODEL:
        # ถ้าตัวกรองความปลอดภัยปฏิเสธ ให้ระบบเรียกโมเดลสำรองต่อในคำขอเดียวกัน
        response = client.beta.messages.create(
            betas=["server-side-fallback-2026-06-01"],
            fallbacks=[{"model": settings.CHATBOT_FALLBACK_MODEL}],
            **kwargs,
        )
    else:
        response = client.messages.create(**kwargs)

    if response.stop_reason == "refusal":
        raise RuntimeError("model refused")
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if not text:
        raise RuntimeError("empty reply")
    return text


def reply(*, history: list[dict], lesson: dict | None = None) -> Reply:
    """lesson = {"title", "course", "category"} เมื่อผู้ใช้อยู่ในหน้าเรียน (โหมดติวเตอร์) ไม่มี = โหมดตอบคำถามทั่วไป"""
    last_user = history[-1]["content"] if history else ""
    if llm_enabled():
        system = (
            knowledge.tutor_system_prompt(lesson=lesson["title"], course=lesson["course"], category=lesson["category"])
            if lesson
            else knowledge.public_system_prompt()
        )
        try:
            return Reply(_call_claude(system, history), "ai", [])
        except (anthropic.APIError, RuntimeError) as exc:
            logger.warning("chatbot LLM failed, using FAQ fallback: %s", exc)
    if lesson:
        return Reply(
            "ตอนนี้ผู้ช่วยติวอัตโนมัติยังไม่พร้อมใช้งาน ลองจดคำถามไว้ในสมุดโน้ตของคลิปนี้ หรือสอบถามผู้ดูแลได้",
            "faq",
            [],
        )
    text, suggestions = faq_bot.answer(last_user)
    return Reply(text, "faq", suggestions)

from apps.learning.models import LessonNote

MAX_NOTE_LENGTH = 20000


def get_note_content(*, user, lesson_id: int) -> str:
    return LessonNote.objects.filter(user=user, lesson_id=lesson_id).values_list("content", flat=True).first() or ""


def save_note(*, user, lesson, content: str) -> LessonNote:
    """บันทึกโน้ตของนักเรียน 1 คน/1 คลิป (upsert) จำกัดความยาวกันข้อมูลบวม"""
    note, _ = LessonNote.objects.update_or_create(
        user=user, lesson=lesson, defaults={"content": str(content)[:MAX_NOTE_LENGTH]}
    )
    return note

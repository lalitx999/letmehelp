from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from apps.learning.models import LessonProgress, StudyLog

MAX_DELTA = 30  # วินาทีสูงสุดที่นับต่อ 1 ครั้งที่ client รายงาน (กันตัวเลขปลอม)
COMPLETE_RATIO = 0.9


def resume_position(last_position: int) -> int:
    """กลับมาเรียนใหม่ → ถอยหลังอัตโนมัติ (ค่าเริ่มต้น 10 วินาที) ไม่ติดลบ"""
    return max(0, last_position - settings.RESUME_REWIND_SECONDS)


def save_progress(*, user, lesson, position: int, watched_delta: int, client_duration: int = 0) -> LessonProgress:
    duration = lesson.duration_seconds or max(0, client_duration)
    position = max(0, position)
    if duration:
        position = min(position, duration)
    delta = max(0, min(watched_delta, MAX_DELTA))
    completed = bool(duration) and position >= duration * COMPLETE_RATIO

    with transaction.atomic():
        progress, created = LessonProgress.objects.get_or_create(
            user=user, lesson=lesson, defaults={"last_position": position, "completed": completed}
        )
        if not created:
            progress.last_position = position
            progress.completed = progress.completed or completed  # เรียนจบแล้วไม่ถอยกลับ
            progress.save(update_fields=["last_position", "completed", "updated_at"])

        if delta:
            _add_study_seconds(user_id=user.pk, lesson_id=lesson.pk, seconds=delta)
    return progress


def _add_study_seconds(*, user_id: int, lesson_id: int, seconds: int) -> None:
    today = timezone.localdate()
    updated = StudyLog.objects.filter(user_id=user_id, lesson_id=lesson_id, date=today).update(
        seconds=F("seconds") + seconds
    )
    if updated:
        return
    try:
        with transaction.atomic():
            StudyLog.objects.create(user_id=user_id, lesson_id=lesson_id, date=today, seconds=seconds)
    except IntegrityError:  # request อื่นสร้างตัดหน้า
        StudyLog.objects.filter(user_id=user_id, lesson_id=lesson_id, date=today).update(
            seconds=F("seconds") + seconds
        )

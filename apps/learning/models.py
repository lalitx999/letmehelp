from django.conf import settings
from django.db import models


class LessonProgress(models.Model):
    """ตำแหน่งวิดีโอล่าสุดของนักเรียนแต่ละคลิป — ใช้เรียนต่อจากเดิม"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lesson_progress")
    lesson = models.ForeignKey("courses.Lesson", on_delete=models.CASCADE, related_name="progress")
    last_position = models.PositiveIntegerField(default=0)  # วินาที
    completed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "lesson"], name="uniq_progress_user_lesson")]
        indexes = [models.Index(fields=["user", "-updated_at"])]


class StudyLog(models.Model):
    """เวลาเรียนจริงต่อวันต่อคลิป — ใช้ทำปฏิทินและสถิติ"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="study_logs")
    lesson = models.ForeignKey("courses.Lesson", on_delete=models.CASCADE, related_name="study_logs")
    date = models.DateField()
    seconds = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "lesson", "date"], name="uniq_studylog_user_lesson_date")]
        indexes = [models.Index(fields=["user", "date"])]


class LessonNote(models.Model):
    """สมุดโน้ตส่วนตัวของนักเรียนต่อ 1 คลิป (รองรับ timestamp แบบ [mm:ss])"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lesson_notes")
    lesson = models.ForeignKey("courses.Lesson", on_delete=models.CASCADE, related_name="notes")
    content = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "lesson"], name="uniq_note_user_lesson")]

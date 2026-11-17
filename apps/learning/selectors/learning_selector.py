import calendar
from datetime import date, timedelta

from django.db.models import Count, Sum
from django.utils import timezone

from apps.courses.models import Lesson
from apps.learning.models import LessonProgress, StudyLog


def get_lesson_with_course(lesson_id):
    return (
        Lesson.objects.select_related("section__course")
        .only(
            "id", "title", "youtube_video_id", "duration_seconds", "is_free_preview",
            "section__id", "section__course_id", "section__course__id", "section__course__slug",
            "section__course__title",
        )
        .filter(pk=lesson_id)
        .first()
    )


def progress_map(user, course_id):
    """{lesson_id: (last_position, completed)} ของคอร์สนี้ ใน query เดียว"""
    rows = LessonProgress.objects.filter(user=user, lesson__section__course_id=course_id).values_list(
        "lesson_id", "last_position", "completed"
    )
    return {lid: (pos, done) for lid, pos, done in rows}


def first_unfinished_lesson_id(course, progress):
    """คลิปแรกที่ยังไม่จบ (ถ้าจบหมดให้คืนคลิปแรก) — course ต้อง prefetch sections/lessons มาแล้ว"""
    first = None
    for section in course.sections.all():
        for lesson in section.lessons.all():
            first = first or lesson.pk
            if not progress.get(lesson.pk, (0, False))[1]:
                return lesson.pk
    return first


def course_progress_percent(user, course_ids):
    """{course_id: percent} — 2 aggregate queries ไม่ว่าจะมีกี่คอร์ส"""
    totals = dict(
        Lesson.objects.filter(section__course_id__in=course_ids)
        .values_list("section__course_id")
        .annotate(n=Count("id"))
    )
    done = dict(
        LessonProgress.objects.filter(user=user, completed=True, lesson__section__course_id__in=course_ids, lesson__deleted_at__isnull=True)
        .values_list("lesson__section__course_id")
        .annotate(n=Count("id"))
    )
    return {cid: round(done.get(cid, 0) * 100 / totals[cid]) if totals.get(cid) else 0 for cid in course_ids}


def month_calendar(user, year: int, month: int):
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    rows = (
        StudyLog.objects.filter(user=user, date__range=(first, last))
        .values("date")
        .annotate(seconds=Sum("seconds"))
        .order_by("date")
    )
    return {r["date"].isoformat(): r["seconds"] for r in rows}


def study_stats(user):
    agg = StudyLog.objects.filter(user=user).aggregate(total=Sum("seconds"), days=Count("date", distinct=True))
    completed = LessonProgress.objects.filter(user=user, completed=True).count()
    dates = sorted(set(StudyLog.objects.filter(user=user).values_list("date", flat=True)))
    date_set = set(dates)
    today = timezone.localdate()

    cursor = today if today in date_set else today - timedelta(days=1)
    streak = 0
    while cursor in date_set:
        streak += 1
        cursor -= timedelta(days=1)

    longest = run = 0
    prev = None
    for d in dates:
        run = run + 1 if prev and d == prev + timedelta(days=1) else 1
        longest = max(longest, run)
        prev = d

    month_seconds = (
        StudyLog.objects.filter(user=user, date__year=today.year, date__month=today.month)
        .aggregate(total=Sum("seconds"))["total"] or 0
    )
    return {
        "total_seconds": agg["total"] or 0,
        "study_days": agg["days"] or 0,
        "completed_lessons": completed,
        "streak": streak,
        "longest_streak": max(longest, streak),
        "month_seconds": month_seconds,
        "studied_today": today in date_set,
    }


def last_studied(user, course_ids):
    """คลิปที่เรียนล่าสุดในคอร์สที่ยังมีสิทธิ์ — ใช้ทำการ์ด 'เรียนต่อ' ในหน้า Dashboard"""
    if not course_ids:
        return None
    return (
        LessonProgress.objects.filter(user=user, lesson__section__course_id__in=course_ids, lesson__deleted_at__isnull=True)
        .select_related("lesson__section__course")
        .only(
            "id", "last_position", "completed", "updated_at",
            "lesson__id", "lesson__title", "lesson__duration_seconds",
            "lesson__section__id", "lesson__section__course__id",
            "lesson__section__course__title", "lesson__section__course__slug",
        )
        .order_by("-updated_at")
        .first()
    )


def week_strip(user):
    """เวลาเรียน 7 วันล่าสุด (เก่า→ใหม่) สำหรับแถบรายสัปดาห์ในแดชบอร์ด — 1 query"""
    today = timezone.localdate()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    rows = (
        StudyLog.objects.filter(user=user, date__gte=days[0])
        .values("date")
        .annotate(seconds=Sum("seconds"))
    )
    by_day = {r["date"]: r["seconds"] for r in rows}
    names = ["จ", "อ", "พ", "พฤ", "ศ", "ส", "อา"]
    return [
        {"label": names[d.weekday()], "seconds": by_day.get(d, 0), "studied": by_day.get(d, 0) > 0, "today": d == today}
        for d in days
    ]

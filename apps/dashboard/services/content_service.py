from django.db import transaction

from apps.courses.models import Lesson, LessonAttachment, Section


@transaction.atomic
def add_section(*, course, title: str, order: int) -> Section:
    return Section.objects.create(course=course, title=title, order=order)


@transaction.atomic
def add_lesson(*, section: Section, form) -> Lesson:
    lesson = form.save(commit=False)
    lesson.section = section
    lesson.save()
    return lesson


def add_attachment(*, lesson: Lesson, form) -> LessonAttachment:
    att = form.save(commit=False)
    att.lesson = lesson
    att.save()
    return att

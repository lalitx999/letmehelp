from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import render

from apps.enrollments.selectors.enrollment_selector import get_active_enrollment

from .selectors import course_selector
from .services.pricing_service import packages_for


def course_list(request):
    category = request.GET.get("category")
    page = Paginator(course_selector.search_published_courses(category), 12).get_page(request.GET.get("page"))
    return render(
        request,
        "courses/list.html",
        {"page": page, "categories": course_selector.list_categories(), "active_category": category},
    )


def course_detail(request, slug):
    course = course_selector.get_published_course_detail(slug)
    if course is None:
        raise Http404
    enrollment = get_active_enrollment(request.user, course.pk) if request.user.is_authenticated else None
    lesson_total = sum(len(s.lessons.all()) for s in course.sections.all())  # ใช้ข้อมูลที่ prefetch แล้ว ไม่ยิง query เพิ่ม
    return render(
        request, "courses/detail.html", {"course": course, "enrollment": enrollment, "lesson_total": lesson_total, "packages": packages_for(course)}
    )

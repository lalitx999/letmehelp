from django.urls import path

from . import views

app_name = "learning"

urlpatterns = [
    path("my-courses/", views.my_courses, name="my_courses"),
    path("study/", views.study_dashboard, name="study"),
    path("study/calendar/", views.calendar_data, name="calendar_data"),
    path("progress/", views.save_progress, name="save_progress"),
    path("notes/<int:lesson_id>/", views.lesson_note, name="note"),
    path("files/<int:attachment_id>/", views.download_attachment, name="attachment"),
    path("<str:slug>/", views.player, name="player"),
    path("<str:slug>/<int:lesson_id>/", views.player, name="player_lesson"),
]

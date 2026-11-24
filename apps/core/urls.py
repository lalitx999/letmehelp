from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("free-trial/", views.free_trial, name="free_trial"),
    path("guide/", views.guide, name="guide"),
    path("about/", views.about, name="about"),
    path("llms.txt", views.llms_txt, name="llms"),
    path("llms-full.txt", views.llms_full_txt, name="llms_full"),
    path("llm.txt", RedirectView.as_view(pattern_name="core:llms", permanent=True)),
    path("llm-full.txt", RedirectView.as_view(pattern_name="core:llms_full", permanent=True)),
    path("privacy/", views.privacy, name="privacy"),
    path("terms/", views.terms, name="terms"),
    path("robots.txt", views.robots_txt, name="robots"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="sw"),
    path("offline/", views.offline, name="offline"),
]

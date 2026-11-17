from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apps.core.sitemaps import SITEMAPS

urlpatterns = [
    # Django admin เดิมเก็บไว้ให้ผู้ดูแลระบบ (superuser) เท่านั้น — ผู้ดูแลเว็บใช้ /dashboard/
    path("django-admin/", admin.site.urls),
    path("dashboard/", include("apps.dashboard.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("courses/", include("apps.courses.urls")),
    path("learn/", include("apps.learning.urls")),
    path("payments/", include("apps.payments.urls")),
    path("chat/", include("apps.chatbot.urls")),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

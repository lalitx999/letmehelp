from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apps.core.sitemaps import SITEMAPS

urlpatterns = [
    path("dashboard/", include("apps.dashboard.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("courses/", include("apps.courses.urls")),
    path("learn/", include("apps.learning.urls")),
    path("payments/", include("apps.payments.urls")),
    path("chat/", include("apps.chatbot.urls")),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("", include("apps.core.urls")),
]

# Django admin หน้าเดิมไม่ใช้กับผู้ใช้งาน (แอดมินเว็บใช้ /dashboard/) — ปิดใน production เพื่อลดช่องโจมตี
# เปิดได้เมื่อจำเป็นด้วย DJANGO_ADMIN_ENABLED=True ใน .env (ตอนพัฒนาเปิดไว้)
if settings.DJANGO_ADMIN_ENABLED:
    urlpatterns.insert(0, path("django-admin/", admin.site.urls))

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.SiteLoginView.as_view(), name="login"),
    path("logout/", views.SiteLogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    path("profile/", views.profile, name="profile"),
    path("password/", views.SitePasswordChangeView.as_view(), name="password_change"),
    path("password/forgot/", views.SitePasswordResetView.as_view(), name="password_reset"),
    path("password/forgot/sent/", views.SitePasswordResetDoneView.as_view(), name="password_reset_done"),
    path("password/reset/<uidb64>/<token>/", views.SitePasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("password/reset/done/", views.SitePasswordResetCompleteView.as_view(), name="password_reset_complete"),
]

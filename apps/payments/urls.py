from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("checkout/<str:slug>/", views.checkout, name="checkout"),
    path("orders/<int:order_id>/slip/", views.upload_slip, name="upload_slip"),
    path("orders/<int:order_id>/status/", views.order_status, name="order_status"),
    path("slips/<int:slip_id>/image/", views.slip_image, name="slip_image"),
]

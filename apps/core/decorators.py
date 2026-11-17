from django.contrib.auth.decorators import user_passes_test

# ใช้กับทุกหน้าใน Custom Admin Dashboard — เช็กสิทธิ์ก่อนเรนเดอร์ทุกครั้ง
staff_required = user_passes_test(
    lambda u: u.is_active and u.is_staff,
    login_url="accounts:login",
)

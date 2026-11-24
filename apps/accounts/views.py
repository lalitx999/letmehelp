from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm as DjangoPasswordResetForm
from django.contrib.auth.views import (
    LoginView, LogoutView, PasswordChangeView, PasswordResetCompleteView, PasswordResetConfirmView, PasswordResetDoneView, PasswordResetView,
)
from django.core.cache import cache
from django.urls import reverse_lazy
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import LoginForm, ProfileForm, RegisterForm
from .services import account_service


class SiteLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class SiteLogoutView(LogoutView):
    pass


def register(request):
    if request.user.is_authenticated:
        return redirect("learning:my_courses")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = account_service.register_student(
            full_name=form.cleaned_data["full_name"],
            phone=form.cleaned_data["phone"],
            email=form.cleaned_data["email"],
            password=form.cleaned_data["password1"],
        )
        login(request, user)
        messages.success(request, "สมัครสมาชิกสำเร็จ ยินดีต้อนรับ!")
        nxt = request.POST.get("next") or request.GET.get("next")
        if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
            return redirect(nxt)
        return redirect("learning:my_courses")
    return render(request, "accounts/register.html", {"form": form, "next": request.GET.get("next", "")})


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "บันทึกข้อมูลแล้ว")
        nxt = request.POST.get("next")
        if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
            return redirect(nxt)
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})


class SitePasswordChangeView(PasswordChangeView):  # PasswordChangeView บังคับล็อกอินอยู่แล้ว
    """เปลี่ยนรหัสผ่าน — เปลี่ยนแล้วไม่ถูกเด้งออกจากระบบ (Django อัปเดต session hash ให้)"""

    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:profile")

    def form_valid(self, form):
        messages.success(self.request, "เปลี่ยนรหัสผ่านแล้ว")
        return super().form_valid(form)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for f in form.fields.values():
            f.widget.attrs["class"] = "form-control"
            f.help_text = ""
        return form


# ---- ลืมรหัสผ่าน / ตั้งรหัสผ่านครั้งแรก (นักเรียนที่แอดมินนำเข้า) ----------------------------------
class SitePasswordResetForm(DjangoPasswordResetForm):
    def get_users(self, email):
        """ของ Django ข้ามบัญชีที่ยังไม่มีรหัสผ่าน — แต่นักเรียนที่แอดมินนำเข้ายังไม่มี จึงต้องรวมด้วย"""
        from .models import User

        return User.objects.filter(email__iexact=email, is_active=True)


class SitePasswordResetView(PasswordResetView):
    template_name = "accounts/password_reset.html"
    form_class = SitePasswordResetForm
    email_template_name = "accounts/email/password_reset.txt"
    subject_template_name = "accounts/email/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")

    def form_valid(self, form):
        # กันยิงขอลิงก์รัวๆ: 5 ครั้ง / 15 นาที ต่อ IP (ตอบเหมือนเดิมเสมอ ไม่บอกว่ามีอีเมลนี้หรือไม่)
        key = f"pwreset:{self.request.META.get('REMOTE_ADDR', '')}"
        n = cache.get(key, 0)
        if n >= 5:
            return redirect(self.success_url)
        cache.set(key, n + 1, 15 * 60)
        return super().form_valid(form)


class SitePasswordResetDoneView(PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class SitePasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")


class SitePasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"

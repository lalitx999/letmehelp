from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
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

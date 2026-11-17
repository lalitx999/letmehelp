from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, BaseUserCreationForm

from .models import User


class RegisterForm(BaseUserCreationForm):
    accept_terms = forms.BooleanField(
        required=True, error_messages={"required": "กรุณายอมรับข้อกำหนดการใช้งานและนโยบายความเป็นส่วนตัว"},
    )

    class Meta:
        model = User
        fields = ("full_name", "phone", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("อีเมลนี้ถูกใช้งานแล้ว")
        return email

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].help_text = ""
        for name, f in self.fields.items():
            f.widget.attrs.update({"class": "form-check-input" if name == "accept_terms" else "form-control form-control-lg"})
        self.fields["full_name"].widget.attrs["placeholder"] = "สมชาย ใจดี"
        self.fields["phone"].widget.attrs.update({"placeholder": "0812345678", "inputmode": "numeric"})


class LoginForm(AuthenticationForm):
    username = forms.EmailField(label="อีเมล", widget=forms.EmailInput(attrs={"autofocus": True}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs.update({"class": "form-control form-control-lg"})

    def clean(self):
        email = self.cleaned_data.get("username", "").lower()
        password = self.cleaned_data.get("password")
        if email and password:
            self.user_cache = authenticate(self.request, username=email, password=password)
            if self.user_cache is None:
                raise forms.ValidationError("อีเมลหรือรหัสผ่านไม่ถูกต้อง")
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("full_name", "phone")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs.update({"class": "form-control"})


class AdminUserForm(forms.ModelForm):
    """ฟอร์มที่แอดมินใช้สร้าง/แก้ไขบัญชี (นักเรียนหรือแอดมิน) — รหัสผ่านเว้นว่างเพื่อให้ระบบสุ่ม"""

    password = forms.CharField(label="รหัสผ่านชั่วคราว", required=False, min_length=8, widget=forms.TextInput(attrs={"autocomplete": "off"}),
                               help_text="เว้นว่างให้ระบบสุ่มให้ (แสดงหลังบันทึก) อย่างน้อย 8 ตัวอักษร")

    class Meta:
        model = User
        fields = ("full_name", "phone", "email", "admin_note")
        widgets = {"admin_note": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, creating=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not creating:
            del self.fields["password"]
        for f in self.fields.values():
            f.widget.attrs["class"] = "form-control"
        self.fields["admin_note"].help_text = "บันทึกภายใน นักเรียนมองไม่เห็น"

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("อีเมลนี้ถูกใช้งานแล้ว")
        return email


class PasswordResetForm(forms.Form):
    password = forms.CharField(label="รหัสผ่านใหม่", required=False, min_length=8, widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
                               help_text="เว้นว่างให้ระบบสุ่มให้ (จะแสดงในข้อความหลังบันทึก)")

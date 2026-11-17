from django import forms
from django.utils import timezone

from apps.accounts.models import User
from apps.courses.models import Course


class GrantForm(forms.Form):
    email = forms.EmailField(label="อีเมลนักเรียน", widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "student@example.com"}))
    course = forms.ModelChoiceField(label="คอร์ส", queryset=Course.objects.none(), widget=forms.Select(attrs={"class": "form-select"}))
    days = forms.IntegerField(label="อายุสิทธิ์ (วัน)", min_value=1, max_value=36500, initial=180, widget=forms.NumberInput(attrs={"class": "form-control"}),
                              help_text="ตลอดชีพใส่ 36500")
    source = forms.ChoiceField(label="ประเภท", choices=[("manual", "แอดมินมอบ (รับเงินนอกระบบ)"), ("comp", "แถม/ทดลองเรียน")], widget=forms.Select(attrs={"class": "form-select"}))
    note = forms.CharField(label="เหตุผล/หมายเหตุ", required=False, max_length=300, widget=forms.TextInput(attrs={"class": "form-control"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["course"].queryset = Course.objects.only("id", "title").order_by("title")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        user = User.objects.filter(email=email, is_staff=False).first()
        if user is None:
            raise forms.ValidationError("ไม่พบนักเรียนที่ใช้อีเมลนี้ (ให้นักเรียนสมัครสมาชิกก่อน หรือสร้างบัญชีในหน้านักเรียน)")
        self.user = user
        return email


class ExtendForm(forms.Form):
    add_days = forms.IntegerField(label="ต่ออายุเพิ่ม (วัน)", required=False, min_value=1, max_value=36500, widget=forms.NumberInput(attrs={"class": "form-control"}),
                                  help_text="นับต่อจากวันหมดอายุเดิม (หรือวันนี้ถ้าหมดแล้ว)")
    expires_on = forms.DateField(label="หรือกำหนดวันหมดอายุเอง", required=False, widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))

    def clean(self):
        data = super().clean()
        if bool(data.get("add_days")) == bool(data.get("expires_on")):
            raise forms.ValidationError("กรอกอย่างใดอย่างหนึ่ง: จำนวนวัน หรือ วันหมดอายุ")
        if data.get("expires_on") and data["expires_on"] < timezone.localdate():
            raise forms.ValidationError("วันหมดอายุต้องไม่ใช่วันที่ผ่านมาแล้ว (ถ้าต้องการปิดสิทธิ์ ให้ใช้ปุ่มยกเลิกสิทธิ์)")
        return data

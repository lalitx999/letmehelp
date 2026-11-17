from django import forms

from apps.core.services import settings_service

from .models import ReportExport


class ReportForm(forms.ModelForm):
    class Meta:
        model = ReportExport
        fields = ["kind", "fmt", "date_from", "date_to"]
        widgets = {
            "date_from": forms.DateInput(attrs={"type": "date"}),
            "date_to": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {"kind": "ประเภทรายงาน", "fmt": "รูปแบบไฟล์", "date_from": "ตั้งแต่วันที่", "date_to": "ถึงวันที่"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs["class"] = "form-select" if isinstance(f.widget, forms.Select) else "form-control"

    def clean(self):
        data = super().clean()
        if data.get("date_from") and data.get("date_to") and data["date_from"] > data["date_to"]:
            raise forms.ValidationError("ช่วงวันที่ไม่ถูกต้อง")
        return data


class SiteSettingsForm(forms.Form):
    PROMPTPAY_ID = forms.CharField(label="PromptPay (เบอร์โทร 10 หลัก หรือเลขบัตร 13 หลัก)", required=False, max_length=20)
    PROMPTPAY_ACCOUNT_NAME = forms.CharField(label="ชื่อบัญชีรับเงิน (ใช้เทียบกับสลิป)", required=False, max_length=120)
    LINE_CONTACT_URL = forms.URLField(label="ลิงก์ LINE ติดต่อเจ้าของ", required=False, help_text="เช่น https://lin.ee/xxxx — แสดงปุ่มคุยกับแอดมินในเว็บ")
    OWNER_NAME = forms.CharField(label="ชื่อผู้ให้บริการ (แสดงในนโยบายและข้อกำหนด)", required=False, max_length=120, help_text="ชื่อ-นามสกุลเจ้าของ หรือชื่อธุรกิจ เว้นว่างจะใช้ชื่อเว็บ")
    CONTACT_EMAIL = forms.EmailField(label="อีเมลติดต่อ (แสดงในนโยบายและ Footer)", required=False)
    SOCIAL_FACEBOOK = forms.URLField(label="Facebook", required=False, help_text="เว้นว่าง = ไม่แสดงไอคอนใน Footer")
    SOCIAL_INSTAGRAM = forms.URLField(label="Instagram", required=False)
    SOCIAL_YOUTUBE = forms.URLField(label="YouTube", required=False)
    SOCIAL_TIKTOK = forms.URLField(label="TikTok", required=False)
    SOCIAL_LEMON8 = forms.URLField(label="Lemon8", required=False)
    EXPIRY_REMINDER_DAYS = forms.CharField(label="แจ้งเตือนก่อนหมดอายุ (วัน คั่นด้วยจุลภาค)", required=False, max_length=40, help_text="เช่น 7,3,1")
    ANNOUNCEMENT = forms.CharField(label="ประกาศบนหัวเว็บ", required=False, max_length=200, help_text="เว้นว่างเพื่อไม่แสดง")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, f in self.fields.items():
            f.widget.attrs["class"] = "form-control"
            if not self.is_bound:
                f.initial = settings_service.get(name)

    def clean_PROMPTPAY_ID(self):
        v = "".join(ch for ch in self.cleaned_data["PROMPTPAY_ID"] if ch.isdigit())
        if v and len(v) not in (10, 13):
            raise forms.ValidationError("ต้องเป็นเบอร์โทร 10 หลัก หรือเลขบัตรประชาชน 13 หลัก")
        return v

    def clean_EXPIRY_REMINDER_DAYS(self):
        raw = self.cleaned_data["EXPIRY_REMINDER_DAYS"].replace(" ", "")
        if raw and not all(x.isdigit() and 0 < int(x) <= 365 for x in raw.split(",")):
            raise forms.ValidationError("ใส่ตัวเลขวัน 1–365 คั่นด้วยจุลภาค เช่น 7,3,1")
        return raw

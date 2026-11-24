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
    PROMPTPAY_BANK_ACCOUNT = forms.CharField(label="เลขบัญชีธนาคารที่ผูกพร้อมเพย์ (ใช้เทียบกับสลิป)", required=False, max_length=20, help_text="เช่น 419-008459-4 — สลิปบางธนาคารแสดงเลขบัญชีแทนเบอร์พร้อมเพย์")
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


class BroadcastForm(forms.Form):
    target = forms.ChoiceField(label="ส่งถึง")
    subject = forms.CharField(label="หัวข้ออีเมล", max_length=150)
    message = forms.CharField(label="ข้อความ", max_length=5000, widget=forms.Textarea(attrs={"rows": 9}),
                              help_text="ระบบใส่ \"สวัสดีค่ะ คุณ(ชื่อนักเรียน)\" ด้านบน และชื่อเว็บไว้ท้ายให้อัตโนมัติ")

    def __init__(self, *args, targets=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target"].choices = [(v, f"{label} — {n:,} คน") for v, label, n in targets]
        for f in self.fields.values():
            f.widget.attrs["class"] = "form-select" if isinstance(f.widget, forms.Select) else "form-control"


class StudentImportForm(forms.Form):
    file = forms.FileField(label="ไฟล์ CSV", help_text="แถวแรกเป็นหัวคอลัมน์: ชื่อ-นามสกุล, อีเมล, เบอร์โทร, วันหมดอายุ (ไม่บังคับ) · ไม่เกิน 2,000 คน")
    course = forms.ModelChoiceField(label="มอบสิทธิ์คอร์ส (ไม่บังคับ)", queryset=None, required=False, empty_label="— ไม่มอบสิทธิ์ สร้างบัญชีอย่างเดียว —")
    days = forms.IntegerField(label="อายุสิทธิ์ (วัน)", required=False, min_value=1, max_value=36500,
                              help_text="ใช้กับแถวที่ไม่มีวันหมดอายุ · เว้นว่าง = ตามอายุคอร์ส · ตลอดชีพ = 36500")
    send_email = forms.BooleanField(label="ส่งอีเมลให้นักเรียนใหม่ตั้งรหัสผ่าน", required=False, initial=True,
                                    help_text="ต้องตั้งค่าอีเมลของเว็บก่อน ถ้ายังไม่ได้ตั้ง ให้นักเรียนกด \"ลืมรหัสผ่าน\" ที่หน้าเข้าสู่ระบบเอง")

    def __init__(self, *args, **kwargs):
        from apps.courses.models import Course

        super().__init__(*args, **kwargs)
        self.fields["course"].queryset = Course.objects.order_by("title")
        for name, f in self.fields.items():
            if name == "send_email":
                f.widget.attrs["class"] = "form-check-input"
            else:
                f.widget.attrs["class"] = "form-select" if isinstance(f.widget, forms.Select) else "form-control"
        self.fields["file"].widget.attrs["accept"] = ".csv,text/csv"

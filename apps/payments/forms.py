from django import forms


class SlipUploadForm(forms.Form):
    image = forms.ImageField(label="สลิปโอนเงิน")

    def clean_image(self):
        img = self.cleaned_data["image"]
        if img.size > 8 * 1024 * 1024:
            raise forms.ValidationError("ไฟล์ใหญ่เกิน 8MB")
        if getattr(img, "content_type", "") not in ("image/jpeg", "image/png", "image/webp"):
            raise forms.ValidationError("รองรับเฉพาะ JPG / PNG / WebP")
        return img


class ManualOrderForm(forms.Form):
    """แอดมินสร้างออเดอร์ให้นักเรียน (จ่ายนอกระบบ)"""

    email = forms.EmailField(label="อีเมลนักเรียน", widget=forms.EmailInput(attrs={"class": "form-control"}))
    course = forms.ModelChoiceField(label="คอร์ส", queryset=None, widget=forms.Select(attrs={"class": "form-select"}))
    amount = forms.DecimalField(label="ยอดเงิน (บาท)", min_value=0, decimal_places=2, widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}))
    days = forms.IntegerField(label="อายุสิทธิ์ (วัน)", min_value=1, max_value=36500, initial=180, widget=forms.NumberInput(attrs={"class": "form-control"}), help_text="ตลอดชีพใส่ 36500")
    paid = forms.BooleanField(label="ชำระเงินแล้ว — เปิดสิทธิ์เรียนทันที", required=False, initial=True, widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))
    note = forms.CharField(label="หมายเหตุ", required=False, max_length=300, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "เช่น โอนเข้าบัญชีส่วนตัว / เงินสด"}))

    def __init__(self, *args, **kwargs):
        from apps.courses.models import Course

        super().__init__(*args, **kwargs)
        self.fields["course"].queryset = Course.objects.only("id", "title").order_by("title")

    def clean_email(self):
        from apps.accounts.models import User

        email = self.cleaned_data["email"].lower()
        user = User.objects.filter(email=email, is_staff=False).first()
        if user is None:
            raise forms.ValidationError("ไม่พบนักเรียนที่ใช้อีเมลนี้")
        self.user = user
        return email


class RefundForm(forms.Form):
    revoke_access = forms.BooleanField(label="เพิกถอนสิทธิ์เรียนของคอร์สนี้ด้วย", required=False, initial=True, widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))
    note = forms.CharField(label="เหตุผล/หมายเหตุ", required=False, max_length=300, widget=forms.TextInput(attrs={"class": "form-control"}))

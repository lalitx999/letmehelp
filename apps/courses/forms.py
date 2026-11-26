from django import forms
from django.utils.text import slugify

from .models import Category, Course, CoursePackage, Lesson, LessonAttachment, Section
from .services.youtube import extract_youtube_id


class _Bootstrap:
    def _style(self):
        for f in self.fields.values():
            w = f.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs["class"] = "form-check-input"
            elif isinstance(w, forms.Select):
                w.attrs["class"] = "form-select"
            else:
                w.attrs["class"] = "form-control"


class CourseForm(_Bootstrap, forms.ModelForm):
    class Meta:
        model = Course
        # เรียงให้ช่องที่เกี่ยวกันอยู่คู่กันในฟอร์ม 2 คอลัมน์: หมวด|slug · ราคา|ราคาโปร · วันสิ้นสุดโปร|อายุคอร์ส
        fields = [
            "title", "subtitle", "category", "slug", "description",
            "price", "promo_price", "promo_ends_on", "access_days", "thumbnail", "cover_url", "book_url", "is_published", "is_featured",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 8}), "promo_ends_on": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}
        labels = {"category": "หมวดคอร์ส", "slug": "ลิงก์คอร์ส (slug)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.only("id", "name")
        self.fields["promo_price"].help_text = "เว้นว่างถ้าไม่มีโปรโมชัน (ต้องต่ำกว่าราคาปกติ และระบุวันสิ้นสุดด้วย)"
        self.fields["promo_ends_on"].help_text = "ใช้ราคาโปรได้ถึงสิ้นวันนี้ แล้วกลับเป็นราคาปกติเอง"
        self.fields["book_url"].help_text = "ลิงก์สินค้าใน Shopee (ถ้ามี) จะแสดงปุ่ม 'สั่งซื้อหนังสือเล่ม' ในหน้าคอร์ส"
        self.fields["slug"].required = False
        self.fields["slug"].help_text = "ใช้ใน URL (ภาษาอังกฤษแนะนำ เช่น tgat-english) เว้นว่างเพื่อสร้างอัตโนมัติ"
        self._style()

    def clean_slug(self):
        slug = self.cleaned_data.get("slug") or slugify(self.cleaned_data.get("title", ""), allow_unicode=True)
        if not slug:
            raise forms.ValidationError("ระบุ slug")
        if Course.all_objects.filter(slug=slug).exclude(pk=self.instance.pk).exists():  # รวมที่อยู่ในถังขยะ (slug ยังถูกจองอยู่)
            raise forms.ValidationError("slug นี้ถูกใช้แล้ว (อาจอยู่ในถังขยะ) กรุณาระบุเอง")
        return slug

    def clean_cover_url(self):
        url = self.cleaned_data.get("cover_url", "").strip()
        if url and not (url.startswith("https://") or url.startswith("http://") or url.startswith("/static/")):
            raise forms.ValidationError("ลิงก์ต้องขึ้นต้นด้วย https:// หรือ /static/")
        return url

    def clean_price(self):
        price = self.cleaned_data["price"]
        if price < 0:
            raise forms.ValidationError("ราคาต้องไม่ติดลบ")
        return price

    def clean_book_url(self):
        url = self.cleaned_data.get("book_url", "").strip()
        if url and not url.startswith("https://"):
            raise forms.ValidationError("ลิงก์ต้องขึ้นต้นด้วย https://")
        return url

    def clean(self):
        data = super().clean()
        promo, ends, price = data.get("promo_price"), data.get("promo_ends_on"), data.get("price")
        if promo is not None:
            if promo < 0:
                self.add_error("promo_price", "ราคาโปรโมชันต้องไม่ติดลบ")
            elif price is not None and promo >= price:
                self.add_error("promo_price", "ราคาโปรโมชันต้องต่ำกว่าราคาปกติ")
            if not ends:
                self.add_error("promo_ends_on", "ระบุวันสิ้นสุดโปรโมชัน")
        elif ends:
            self.add_error("promo_price", "ระบุราคาโปรโมชัน หรือเอาวันสิ้นสุดออก")
        return data

    def clean_access_days(self):
        days = self.cleaned_data["access_days"]
        if days < 1:
            raise forms.ValidationError("อายุคอร์สต้องอย่างน้อย 1 วัน")
        return days


class SectionForm(_Bootstrap, forms.ModelForm):
    class Meta:
        model = Section
        fields = ["title", "order"]
        labels = {"title": "ชื่อบท", "order": "ลำดับ"}
        help_texts = {"order": "จัดลำดับง่ายกว่าด้วยการลากในหน้าเนื้อหาคอร์ส"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()


class LessonForm(_Bootstrap, forms.ModelForm):
    youtube_url = forms.CharField(label="ลิงก์ YouTube (Unlisted)")
    # แนบ PDF ได้ในฟอร์มเดียวกัน (ไม่บังคับ) — เพิ่มทีละไฟล์ ไฟล์เดิมยังอยู่
    pdf_file = forms.FileField(label="แนบไฟล์ PDF (ไม่บังคับ)", required=False, help_text="PDF ไม่เกิน 25MB · มีไฟล์เดิมอยู่แล้วจะเพิ่มเป็นไฟล์ใหม่")
    pdf_title = forms.CharField(label="ชื่อไฟล์ที่นักเรียนเห็น", required=False, max_length=160, help_text="เว้นว่าง = ใช้ชื่อไฟล์")

    class Meta:
        model = Lesson
        fields = ["title", "youtube_url", "duration_seconds", "order", "is_free_preview"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["youtube_url"].initial = self.instance.youtube_video_id
        self.fields["order"].label = "ลำดับ"
        self.fields["order"].help_text = "จัดลำดับง่ายกว่าด้วยการลากในหน้าเนื้อหาคอร์ส"
        self._style()

    def clean_youtube_url(self):
        vid = extract_youtube_id(self.cleaned_data["youtube_url"])
        if not vid:
            raise forms.ValidationError("ลิงก์ YouTube ไม่ถูกต้อง")
        return vid

    def clean_pdf_file(self):
        f = self.cleaned_data.get("pdf_file")
        if f and not f.name.lower().endswith(".pdf"):
            raise forms.ValidationError("รองรับเฉพาะไฟล์ PDF")
        if f and f.size > 25 * 1024 * 1024:
            raise forms.ValidationError("ไฟล์ใหญ่เกิน 25MB")
        return f

    def save(self, commit=True):
        self.instance.youtube_video_id = self.cleaned_data["youtube_url"]
        return super().save(commit=commit)


class AttachmentForm(_Bootstrap, forms.ModelForm):
    class Meta:
        model = LessonAttachment
        fields = ["title", "file"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()

    def clean_file(self):
        f = self.cleaned_data["file"]
        if not f.name.lower().endswith(".pdf"):
            raise forms.ValidationError("รองรับเฉพาะไฟล์ PDF")
        if f.size > 25 * 1024 * 1024:
            raise forms.ValidationError("ไฟล์ใหญ่เกิน 25MB")
        return f


class PackageForm(_Bootstrap, forms.ModelForm):
    class Meta:
        model = CoursePackage
        fields = ["label", "days", "price", "is_active"]

    def __init__(self, *args, **kwargs):
        self.course = kwargs.pop("course", None)
        super().__init__(*args, **kwargs)
        self._style()

    def clean_days(self):
        days = self.cleaned_data["days"]
        if days < 1:
            raise forms.ValidationError("อายุต้องอย่างน้อย 1 วัน")
        if self.course and (days == self.course.access_days or
                            CoursePackage.objects.filter(course=self.course, days=days).exclude(pk=self.instance.pk).exists()):
            raise forms.ValidationError("มีแพ็กเกจอายุนี้อยู่แล้ว (แพ็กเกจหลักใช้อายุเดียวกัน หรือซ้ำกับแพ็กเกจอื่น)")
        return days


class CategoryForm(_Bootstrap, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "slug", "description", "order", "is_active"]
        labels = {"name": "ชื่อหมวด", "slug": "slug (ใน URL)", "description": "คำอธิบายสั้น", "order": "ลำดับ", "is_active": "แสดงบนเว็บ"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["slug"].help_text = "ภาษาอังกฤษแนะนำ เช่น tgat เว้นว่างเพื่อสร้างอัตโนมัติ"
        self._style()

    def clean_slug(self):
        slug = self.cleaned_data.get("slug") or slugify(self.cleaned_data.get("name", ""), allow_unicode=True)
        if not slug:
            raise forms.ValidationError("ระบุ slug")
        if Category.all_objects.filter(slug=slug).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("slug นี้ถูกใช้แล้ว (อาจอยู่ในถังขยะ)")
        return slug

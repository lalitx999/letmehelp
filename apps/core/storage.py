"""Storage สำหรับไฟล์ส่วนตัว (สลิป, PDF ประกอบการเรียน, รายงาน) — ไม่มี URL สาธารณะ"""
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateStorage(FileSystemStorage):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("location", str(settings.PRIVATE_MEDIA_ROOT))
        kwargs.setdefault("base_url", None)
        super().__init__(*args, **kwargs)

    def url(self, name):
        raise ValueError("ไฟล์ส่วนตัวต้องดาวน์โหลดผ่าน view ที่ตรวจสิทธิ์เท่านั้น")


private_storage = PrivateStorage()

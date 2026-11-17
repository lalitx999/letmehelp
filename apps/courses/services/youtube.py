import re

_ID = r"[A-Za-z0-9_-]{11}"
_PATTERNS = [
    re.compile(rf"(?:youtube\.com/watch\?(?:.*&)?v=)({_ID})"),
    re.compile(rf"youtu\.be/({_ID})"),
    re.compile(rf"youtube(?:-nocookie)?\.com/(?:embed|shorts|live)/({_ID})"),
]


def extract_youtube_id(value: str) -> str | None:
    """รับลิงก์ YouTube รูปแบบใดก็ได้ หรือ video id ตรงๆ คืนค่า id 11 ตัวอักษร"""
    value = (value or "").strip()
    if re.fullmatch(_ID, value):
        return value
    for pattern in _PATTERNS:
        m = pattern.search(value)
        if m:
            return m.group(1)
    return None

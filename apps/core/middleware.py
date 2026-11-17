class NoCacheStaticMiddleware:
    """เฉพาะตอนพัฒนา: ไม่ให้เบราว์เซอร์ cache ไฟล์ static เพื่อเห็นการแก้ CSS/JS ทันที"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/static/"):
            response["Cache-Control"] = "no-cache, must-revalidate"
        return response

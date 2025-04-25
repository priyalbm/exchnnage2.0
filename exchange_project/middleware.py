from django.http import HttpResponse
from notifications.models import NotificationSetting

class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        settings = NotificationSetting.get_settings()
        if settings and settings.site_maintenance:
            return HttpResponse("Site is under maintenance. Please try again later.", status=503)
        return self.get_response(request)

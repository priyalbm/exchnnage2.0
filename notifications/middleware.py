# notifications/middleware.py
from django.shortcuts import render
from django.urls import resolve
from .models import MaintenanceMode

class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if current URL is in admin or API paths that should bypass maintenance
        current_url = request.path_info
        
        # Bypass maintenance mode for admin, API with JWT token, or the maintenance page itself
        if (current_url.startswith('/admin/') or 
            current_url.startswith('/api/') and 'Authorization' in request.headers or
            current_url == '/maintenance/'):
            return self.get_response(request)
        
        # Check if maintenance mode is active
        maintenance = MaintenanceMode.objects.first()
        if maintenance and maintenance.is_currently_active():
            context = {
                'message': maintenance.message,
                'end_time': maintenance.end_time
            }
            return render(request, 'notifications/maintenance.html', context, status=503)
        
        return self.get_response(request)
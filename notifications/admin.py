from django.contrib import admin
from .models import NotificationSetting

@admin.register(NotificationSetting)
class NotificationSettingAdmin(admin.ModelAdmin):
    list_display = ('site_maintenance', 'expiry_notification', 'policy_change_notification')

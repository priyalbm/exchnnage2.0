from django.db import models

class NotificationSetting(models.Model):
    site_maintenance = models.BooleanField(default=False)
    expiry_notification = models.BooleanField(default=True)
    policy_change_notification = models.BooleanField(default=True)

    def __str__(self):
        return "Notification Settings"

    @classmethod
    def get_settings(cls):
        return cls.objects.first()

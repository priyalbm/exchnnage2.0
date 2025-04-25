from rest_framework import serializers
from .models import NotificationSetting

class NotificationSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationSetting
        fields = '__all__'

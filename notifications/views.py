from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from .models import NotificationSetting
from .serializers import NotificationSettingSerializer

class NotificationSettingsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        settings = NotificationSetting.objects.first()
        if not settings:
            settings = NotificationSetting.objects.create()
        return Response(NotificationSettingSerializer(settings).data)

    def put(self, request):
        settings = NotificationSetting.objects.first()
        if not settings:
            settings = NotificationSetting.objects.create()
        serializer = NotificationSettingSerializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

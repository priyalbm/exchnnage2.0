from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BotConfigurationViewSet, 
    BotTradeLogViewSet, 
    BotPerformanceViewSet
)

router = DefaultRouter()
router.register('bot-configs', BotConfigurationViewSet, basename='botconfig')
router.register('trade-logs', BotTradeLogViewSet, basename='tradelog')
router.register('performance', BotPerformanceViewSet, basename='performance')

urlpatterns = [
    path('', include(router.urls)),
]
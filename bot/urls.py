from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'exchanges', views.ExchangeViewSet)
router.register(r'bots', views.BotConfigViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('pairs/', views.TradingPairAPIView.as_view(), name='trading-pairs'),
    path('bot/start/', views.BotStartView.as_view(), name='bot-start'),
    path('bot/stop/', views.BotStopView.as_view(), name='bot-stop'),
    path('bot/status/', views.BotStatusView.as_view(), name='bot-status'),
    path('logs/', views.BotLogView.as_view(), name='bot-logs'),
    path('bot/orders/', views.BotOrderView.as_view(), name='bot-orders'),
    path('bot/wallet/', views.BotWalletBalanceView.as_view(), name='bot-wallet'),
]
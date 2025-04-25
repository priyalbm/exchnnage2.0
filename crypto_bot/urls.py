from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ExchangeViewSet, ExchangeConfigViewSet, 
    BotConfigViewSet, OrderViewSet, TradingPairsAPIView,
    BotMonitorView
)

router = DefaultRouter()
router.register(r'exchanges', ExchangeViewSet, basename='exchange')
router.register(r'exchange-configs', ExchangeConfigViewSet, basename='exchange-config')
router.register(r'bots', BotConfigViewSet, basename='bot')
router.register(r'orders', OrderViewSet, basename='order')

urlpatterns = [
    path('', include(router.urls)),
    path('trading-pairs/', TradingPairsAPIView.as_view(), name='trading-pairs'),
    path('bot-monitor/', BotMonitorView.as_view(), name='bot-monitor'),
    
    # Bot specific action endpoints
    path('bots/<int:pk>/start/', BotConfigViewSet.as_view({'post': 'start'}), name='bot-start'),
    path('bots/<int:pk>/stop/', BotConfigViewSet.as_view({'post': 'stop'}), name='bot-stop'),
    path('bots/<int:pk>/status/', BotConfigViewSet.as_view({'get': 'status'}), name='bot-status'),
    path('bots/<int:pk>/reset/', BotConfigViewSet.as_view({'post': 'reset'}), name='bot-reset'),
    path('bots/active/', BotConfigViewSet.as_view({'get': 'active_bots'}), name='active-bots'),
]

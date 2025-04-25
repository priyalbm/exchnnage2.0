from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import BotConfiguration, BotTradeLog, BotPerformanceMetrics
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import SearchFilter
from .serializers import (
    BotConfigurationSerializer, 
    BotTradeLogSerializer, 
    BotPerformanceMetricsSerializer
)
from rest_framework.exceptions import ValidationError
from .tasks import execute_bot_trade
from django.contrib.auth import get_user_model
User = get_user_model()


class BotPagination(PageNumberPagination):
    page_size = 1  # Limit to 10 users per page
    page_size_query_param = 'page_size'  # Allow the client to modify the page size via the URL
    max_page_size = 100  # Optional, set a maximum limit on page size


class BotConfigurationViewSet(viewsets.ModelViewSet):
    serializer_class = BotConfigurationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = BotPagination  
    filter_backends = (SearchFilter,)  
    search_fields = ['name',]
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']  # Explicitly allow PUT and PATCH

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return BotConfiguration.objects.all()
        return BotConfiguration.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    def perform_update(self, serializer):
        # Ensure users can only update their own bots unless they're staff/superuser
        instance = self.get_object()
        if instance.user != self.request.user and not (self.request.user.is_staff or self.request.user.is_superuser):
            raise permissions.PermissionDenied("You don't have permission to update this bot configuration.")
        serializer.save()
    
    def perform_destroy(self, instance):
        # Ensure users can only delete their own bots unless they're staff/superuser
        if instance.user != self.request.user and not (self.request.user.is_staff or self.request.user.is_superuser):
            raise permissions.PermissionDenied("You don't have permission to delete this bot configuration.")
        
        # Check if the bot is active before deleting
        if instance.is_active:
            raise ValidationError({"non_field_errors": ["Cannot delete an active bot. Please stop the bot first."]})
        
        instance.delete()
    
    # Handle PUT requests explicitly if needed
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    # Handle PATCH requests explicitly
    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    @action(detail=True, methods=['POST'])
    def start_bot(self, request, pk=None):
        bot_config = self.get_object()
        print(bot_config, "bot_configbot_configbot_config")
        if not bot_config.api_key:
            raise ValidationError({'api_key': 'API key is required to start the bot.'})
        
        if not bot_config.secret_key:
            raise ValidationError({'secret_key': 'Secret key is required to start the bot.'})
        
        if not bot_config.coin_pair:
            raise ValidationError({'coin_pair': 'Coin pair must be specified.'})
        
        try:
            # decrypted_api_key = bot_config.get_decrypted_api_key()
            # if not decrypted_api_key:
            #     raise ValidationError({'api_key': 'Unable to decrypt API key.'})
            
            bot_config.is_active = True
            bot_config.save()
            execute_bot_trade(bot_config.id)
            
            return Response({'status': 'Bot started successfully'}, status=status.HTTP_200_OK)
        
        except Exception as e:
            # Log the error and return a clear error response
            return Response({
                'status': 'Bot start failed', 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    
    @action(detail=True, methods=['POST'])
    def stop_bot(self, request, pk=None):
        bot_config = self.get_object()
        bot_config.is_active = False
        bot_config.save()
        
        return Response({'status': 'Bot stopped'}, status=status.HTTP_200_OK)

class BotTradeLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BotTradeLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user_bots = BotConfiguration.objects.filter(user=self.request.user)
        return BotTradeLog.objects.filter(bot_config__in=user_bots)

class BotPerformanceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BotPerformanceMetricsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user_bots = BotConfiguration.objects.filter(user=self.request.user)
        return BotPerformanceMetrics.objects.filter(bot_config__in=user_bots)
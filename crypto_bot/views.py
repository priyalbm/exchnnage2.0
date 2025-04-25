from rest_framework import viewsets, views, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404, render
from django.conf import settings
import json
import asyncio
import logging
from django.db import IntegrityError
from .models import Exchange, ExchangeConfig, BotConfig, Order
from .serializers import (
    ExchangeSerializer, ExchangeConfigSerializer, 
    BotConfigSerializer, OrderSerializer, TradingPairSerializer
)
import asyncio
from asgiref.sync import async_to_sync
from django.http import Http404
from .utils import get_exchange_client
from .utilssss import trading_bot

logger = logging.getLogger(__name__)


class ExchangeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for the Exchange model
    """
    queryset = Exchange.objects.all()
    serializer_class = ExchangeSerializer
    permission_classes = [permissions.IsAuthenticated]

class ExchangeConfigViewSet(viewsets.ModelViewSet):
    """
    ViewSet for the ExchangeConfig model
    """
    queryset = ExchangeConfig.objects.all()
    serializer_class = ExchangeConfigSerializer
    permission_classes = [permissions.AllowAny]  # Temporarily allow any access for testing
    
    def get_queryset(self):
        # Handle anonymous users for testing
        if not self.request.user.is_authenticated:
            return ExchangeConfig.objects.all()
        # Filter by user if not admin
        elif not self.request.user.is_staff:
            return ExchangeConfig.objects.filter(user=self.request.user)
        return ExchangeConfig.objects.all()
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            self.perform_create(serializer)
        except IntegrityError:
            return Response(
                {"error": "Exchange config already exists for this user and exchange."},
                status=status.HTTP_400_BAD_REQUEST
            )

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['get'])
    def symbols(self, request, pk=None):
        """
        Get available trading pairs from the exchange
        """
        config = self.get_object()
        client = self._get_exchange_client(config)
        
        try:
            result = client.get_trading_pairs()
            if result.get('error'):
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
            return Response(result)
        except Exception as e:
            logger.error(f"Error fetching symbols: {str(e)}")
            return Response(
                {"error": True, "detail": f"Failed to fetch symbols: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def balance(self, request, pk=None):
        """
        Get account balance from the exchange
        """
        config = self.get_object()
        client = self._get_exchange_client(config)
        
        try:
            result = client.get_balance()
            if result.get('error'):
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
            return Response(result)
        except Exception as e:
            logger.error(f"Error fetching balance: {str(e)}")
            return Response(
                {"error": True, "detail": f"Failed to fetch balance: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def ticker(self, request, pk=None):
        """
        Get ticker data for a symbol
        """
        config = self.get_object()
        client = self._get_exchange_client(config)
        symbol = request.query_params.get('symbol')
        
        if not symbol:
            return Response(
                {"error": True, "detail": "Symbol parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            result = client.get_ticker(symbol)
            if result.get('error'):
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
            return Response(result)
        except Exception as e:
            logger.error(f"Error fetching ticker: {str(e)}")
            return Response(
                {"error": True, "detail": f"Failed to fetch ticker: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def order_book(self, request, pk=None):
        """
        Get order book for a symbol
        """
        config = self.get_object()
        client = self._get_exchange_client(config)
        symbol = request.query_params.get('symbol')
        
        if not symbol:
            return Response(
                {"error": True, "detail": "Symbol parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            result = client.get_order_book(symbol)
            if result.get('error'):
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
            return Response(result)
        except Exception as e:
            logger.error(f"Error fetching order book: {str(e)}")
            return Response(
                {"error": True, "detail": f"Failed to fetch order book: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_exchange_client(self, config):
        """
        Helper method to get exchange client
        """
        base_url = config.base_url or config.exchange.base_url
        return get_exchange_client(
            config.exchange.code,
            config.api_key,
            config.api_secret,
            base_url
        )

class BotConfigViewSet(viewsets.ModelViewSet):
    """
    ViewSet for the BotConfig model with enhanced bot control features
    """
    queryset = BotConfig.objects.all()
    serializer_class = BotConfigSerializer
    permission_classes = [permissions.AllowAny]  # Temporarily allow any access for testing
    
    def get_queryset(self):
        # Handle anonymous users for testing
        if not self.request.user.is_authenticated:
            return BotConfig.objects.all()
        # Filter by user if not admin
        elif not self.request.user.is_staff:
            return BotConfig.objects.filter(user=self.request.user)
        return BotConfig.objects.all()
    
    def perform_create(self, serializer):
        # Associate with current user
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """
        Start the trading bot
        """
        bot_config = self.get_object()
        
        # Check if bot can be started
        if bot_config.status == 'running':
            return Response({
                "error": True, 
                "detail": f"Bot is already in {bot_config.status} state"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if bot has any remaining volume
        if bot_config.remaining_volume <= 0:
            return Response({
                "error": True,
                "detail": "Bot has no remaining volume to trade"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Run in event loop using async_to_sync
            result = async_to_sync(trading_bot.run_trading_bot)(bot_config.id)
            print(result,'result')
            if result.get('error', False):
                return Response(
                    {"error": True, "detail": result.get('detail', 'Unknown error')}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Return success response
            return Response({
                "error": False, 
                "data": {
                    "status": "started", 
                    "bot_id": bot_config.id,
                    "name": bot_config.name,
                    "symbol": bot_config.symbol
                }
            })
        except Exception as e:
            logger.error(f"Error starting bot: {str(e)}")
            return Response({
                "error": True, 
                "detail": f"Failed to start bot: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def stop(self, request, pk=None):
        """
        Stop the trading bot
        """
        bot_config = self.get_object()
        
        # Check if bot is actually running
        if bot_config.status != 'running':
            return Response({
                "error": False, 
                "data": {
                    "status": bot_config.status, 
                    "message": f"Bot is already in {bot_config.status} state",
                    "bot_id": bot_config.id
                }
            })
        
        try:
            # Run in event loop using async_to_sync
            result = async_to_sync(trading_bot.stop_bot)(bot_config.id)

            if result.get('error', False):
                return Response(
                    {"error": True, "detail": result.get('detail', 'Unknown error')}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Return success response
            return Response({
                "error": False, 
                "data": {
                    "status": "stopped", 
                    "bot_id": bot_config.id,
                    "name": bot_config.name
                }
            })
        except Exception as e:
            logger.error(f"Error stopping bot: {str(e)}")
            return Response({
                "error": True, 
                "detail": f"Failed to stop bot: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """
        Get the detailed status of the trading bot
        """
        bot_config = self.get_object()
        
        # Return detailed bot status
        return Response({
            "error": False,
            "data": {
                "id": bot_config.id,
                "name": bot_config.name,
                "symbol": bot_config.symbol,
                "status": bot_config.status,
                "total_order_volume": bot_config.total_order_volume,
                "remaining_volume": bot_config.remaining_volume,
                "completed_volume": bot_config.completed_volume,
                "total_orders": bot_config.total_orders,
                "successful_orders": bot_config.successful_orders,
                "last_run": bot_config.last_run,
                "error_message": bot_config.error_message,
                "created_at": bot_config.created_at,
                "updated_at": bot_config.updated_at
            }
        })
    
    @action(detail=True, methods=['post'])
    def reset(self, request, pk=None):
        """
        Reset a bot that is in error or completed state
        """
        bot_config = self.get_object()
        
        # Check if bot can be reset
        if bot_config.status in ['running']:
            return Response({
                "error": True, 
                "detail": "Cannot reset a running bot. Stop it first."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Reset error state and message if present
            bot_config.status = 'idle'
            bot_config.error_message = None
            
            # Check if we need to reset volume too
            reset_volume = request.data.get('reset_volume', False)
            if reset_volume:
                bot_config.remaining_volume = bot_config.total_order_volume
                bot_config.completed_volume = 0
            
            bot_config.save()
            
            return Response({
                "error": False,
                "data": {
                    "id": bot_config.id,
                    "status": "idle",
                    "message": "Bot has been reset successfully"
                }
            })
        except Exception as e:
            logger.error(f"Error resetting bot: {str(e)}")
            return Response({
                "error": True, 
                "detail": f"Failed to reset bot: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])  
    def active_bots(self, request):
        """
        Get list of all currently active bots
        """
        # Import here to avoid circular import
        from .utilssss.trading_bot import RUNNING_BOTS
        
        active_bots = []
        queryset = self.get_queryset().filter(status='running')
        
        for bot in queryset:
            is_actually_running = bot.id in RUNNING_BOTS
            
            # If bot is marked as running but not in RUNNING_BOTS, it's "zombie"
            if not is_actually_running:
                bot.status = 'error'
                bot.error_message = "Bot marked as running but not found in active tasks"
                bot.save()
            else:
                active_bots.append({
                    'id': bot.id,
                    'name': bot.name,
                    'symbol': bot.symbol,
                    'status': bot.status,
                    'last_run': bot.last_run,
                    'total_orders': bot.total_orders,
                    'successful_orders': bot.successful_orders,
                    'completed_volume': bot.completed_volume,
                    'remaining_volume': bot.remaining_volume,
                })
                
        return Response({
            'error': False,
            'data': {
                'active_bots_count': len(active_bots),
                'active_bots': active_bots
            }
        })

class OrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for the Order model
    """
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.AllowAny]  # Temporarily allow any access for testing
    
    def get_queryset(self):
        # Handle anonymous users for testing
        if not self.request.user.is_authenticated:
            return Order.objects.all()
        # Filter by user if not admin
        elif not self.request.user.is_staff:
            return Order.objects.filter(user=self.request.user)
        return Order.objects.all()
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def bot_orders(self, request):
        """
        Get orders for a specific bot
        """
        bot_id = request.query_params.get('bot_id')
        if not bot_id:
            return Response({
                "error": True, 
                "detail": "Bot ID parameter is required"
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Get the bot config (with permission check)
        try:
            # Handle anonymous users for testing
            if not request.user.is_authenticated:
                bot_config = BotConfig.objects.filter(id=bot_id).first()
            else:
                bot_config = BotConfig.objects.filter(user=request.user, id=bot_id).first()
            
            if not bot_config:
                return Response({
                    "error": True, 
                    "detail": "Bot not found or you don't have permission"
                }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "error": True, 
                "detail": f"Error fetching bot: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        # Get orders for this bot
        orders = self.get_queryset().filter(bot_config=bot_config).order_by('-created_at')
        page = self.paginate_queryset(orders)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(orders, many=True)
        return Response({
            "error": False,
            "data": serializer.data
        })

class TradingPairsAPIView(views.APIView):
    """
    API endpoint to get trading pairs from specified exchange
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        exchange_id = request.query_params.get('exchange_id')
        if not exchange_id:
            return Response({
                "error": True, 
                "detail": "Exchange ID parameter is required"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get exchange config for this user and exchange
            exchange_config = ExchangeConfig.objects.filter(
                user=request.user,
                exchange_id=exchange_id,
                is_active=True
            ).first()
            
            if not exchange_config:
                return Response({
                    "error": True, 
                    "detail": "Exchange configuration not found"
                }, status=status.HTTP_404_NOT_FOUND)
                
            # Get exchange client
            client = get_exchange_client(
                exchange_config.exchange.code,
                exchange_config.api_key,
                exchange_config.api_secret,
                exchange_config.base_url or exchange_config.exchange.base_url
            )
            
            if not client:
                return Response({
                    "error": True, 
                    "detail": "Failed to initialize exchange client"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
            # Get trading pairs
            result = client.get_trading_pairs()
            if result.get('error', False):
                return Response({
                    "error": True, 
                    "detail": result.get('detail', 'Unknown error fetching trading pairs')
                }, status=status.HTTP_400_BAD_REQUEST)
                
            # Serialize and return data
            serializer = TradingPairSerializer(result.get('data', []), many=True)
            return Response({
                "error": False,
                "data": serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error fetching trading pairs: {str(e)}")
            return Response({
                "error": True, 
                "detail": f"Failed to fetch trading pairs: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class BotMonitorView(views.APIView):
    """
    View for monitoring all trading bots
    """
    permission_classes = [permissions.AllowAny]  # Temporarily allow any access for testing
    
    def get(self, request):
        """Render the bot monitor page"""
        try:
            # For testing purposes, handle unauthenticated users
            if not request.user.is_authenticated:
                context = {
                    'bots': [],
                    'status_counts': {'running': 0, 'idle': 0, 'stopped': 0, 'completed': 0, 'error': 0, 'total': 0},
                    'exchanges': [],
                    'message': "You are viewing in unauthenticated mode. Some features will be limited."
                }
                return render(request, 'bot_monitor.html', context)
            
            # Get user's bots for initial rendering
            user_bots = BotConfig.objects.filter(user=request.user).order_by('-updated_at')
            
            # Count of bots by status
            status_counts = {
                'running': user_bots.filter(status='running').count(),
                'idle': user_bots.filter(status='idle').count(),
                'stopped': user_bots.filter(status='stopped').count(),
                'completed': user_bots.filter(status='completed').count(),
                'error': user_bots.filter(status='error').count(),
                'total': user_bots.count()
            }
            
            # Get user's exchanges for form selection
            user_exchanges = ExchangeConfig.objects.filter(
                user=request.user,
                is_active=True
            ).select_related('exchange')
            
            context = {
                'bots': user_bots[:10],  # Just first 10 for initial page load
                'status_counts': status_counts,
                'exchanges': user_exchanges,
            }
            
            return render(request, 'bot_monitor.html', context)
            
        except Exception as e:
            logger.error(f"Error rendering bot monitor page: {str(e)}")
            context = {
                'error': f"Error loading page: {str(e)}"
            }
            return render(request, 'bot_monitor.html', context)

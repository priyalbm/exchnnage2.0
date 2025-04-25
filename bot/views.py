import logging
import asyncio
import threading
import traceback
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status,permissions,serializers
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ExchangeConfig, BotConfig, BotLog,Order
from .serializers import (
    ExchangeConfigSerializer, BotConfigSerializer,
    BotLogSerializer, BotStartSerializer, BotStopSerializer,OrderSerializer
)
# Import the mock engine instead of the real engine for now
from .mock_engine import MockBotManager
from .exchanges import get_exchange_client

# Set up logger
logger = logging.getLogger('bot')

# Initialize the bot manager using our simplified mock version
bot_manager = MockBotManager()

# Log initialization
logger.info("Mock Bot Manager initialized - using test mode for bot operations")


class ExchangeViewSet(viewsets.ModelViewSet):
    """
    API endpoint to manage supported exchanges.
    GET: List all exchanges
    POST: Add a new exchange
    PUT/PATCH: Update an exchange
    DELETE: Remove an exchange
    """
    queryset = ExchangeConfig.objects.all()
    serializer_class = ExchangeConfigSerializer


class TradingPairAPIView(APIView):
    """
    API endpoint to fetch trading pairs directly from an exchange.
    Requires API key and secret to fetch real-time data.
    """
    def post(self, request):
        exchange_name = request.data.get('exchange')
        api_key = request.data.get('api_key')
        secret_key = request.data.get('secret_key')
        
        if not exchange_name:
            return Response({
                'error': 'Exchange name is required'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        if not api_key or not secret_key:
            return Response({
                'error': 'API key and secret key are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Try to get exchange client
            exchange_client = get_exchange_client(exchange_name, api_key, secret_key)
            
            # Get the event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Run the get_pairs method
            try:
                # Initialize client if needed
                if hasattr(exchange_client, '_init_client'):
                    loop.run_until_complete(exchange_client._init_client())
                
                # Get pairs from exchange
                pairs = loop.run_until_complete(exchange_client.get_pairs())
                return Response({
                    'pairs': pairs
                })
            finally:
                # Close the loop
                loop.close()
                
        except ValueError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error fetching pairs: {str(e)}")
            return Response({
                'error': f"Error fetching pairs: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BotConfigViewSet(viewsets.ModelViewSet):
    """
    API endpoint to manage bot configurations.
    GET: List all bot configurations
    POST: Create a new bot configuration
    PUT/PATCH: Update a bot configuration
    DELETE: Remove a bot configuration
    """
    queryset = BotConfig.objects.all()
    serializer_class = BotConfigSerializer
    def perform_create(self, serializer):
        # Get user_id from the request data
        user_id = self.request.data.get('user_id')
        if not user_id:
            # If user_id not in request data, try to get it from the authenticated user
            if self.request.user.is_authenticated:
                user_id = self.request.user.id
            else:
                # If still no user_id, raise an error
                raise serializers.ValidationError({"user_id": "This field is required."})
        
        # Save with the user_id
        serializer.save(user_id=user_id)
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a bot (set is_active=True)"""
        bot = self.get_object()
        if bot.is_active:
            return Response({'message': f'Bot {pk} is already active'}, status=status.HTTP_200_OK)
        
        bot.is_active = True
        bot.status = 'running'
        
        bot.save()
        
        # Start the bot via BotManager
        success = bot_manager.start_bot(bot.id)
        
        if success:
            logger.info(f"Bot {bot.id} activated successfully")
            return Response({'message': f'Bot {pk} activated successfully'}, status=status.HTTP_200_OK)
        else:
            # If starting fails, set is_active back to False
            bot.is_active = False
            bot.status = 'stopped'

            bot.save()
            logger.error(f"Failed to activate bot {bot.id}")
            return Response({'error': f'Failed to activate bot {pk}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a bot (set is_active=False)"""
        bot = self.get_object()
        if not bot.is_active:
            return Response({'message': f'Bot {pk} is already inactive'}, status=status.HTTP_200_OK)
        
        # Stop the bot via BotManager
        success = bot_manager.stop_bot(bot.id)
        
        if success:
            bot.is_active = False
            bot.status = 'stopped'
            bot.save()
            logger.info(f"Bot {bot.id} deactivated successfully")
            return Response({'message': f'Bot {pk} deactivated successfully'}, status=status.HTTP_200_OK)
        else:
            logger.error(f"Failed to deactivate bot {bot.id}")
            return Response({'error': f'Failed to deactivate bot {pk}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BotStatusView(APIView):
    """
    API endpoint to check bot status.
    """
    def get(self, request):
        active_bots = BotConfig.objects.filter(is_active=True)
        bot_id = request.query_params.get('bot_id')
        
        if bot_id:
            bot = get_object_or_404(BotConfig, id=bot_id)
            serializer = BotConfigSerializer(bot)
            return Response(serializer.data)
        
        serializer = BotConfigSerializer(active_bots, many=True)
        return Response({
            'active_bots': serializer.data,
            'total_active': active_bots.count()
        })


class BotStartView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    """
    API endpoint to start a trading bot.
    """
    def post(self, request):
        serializer = BotStartSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            user = request.user
            # Get or create exchange config
            exchange, _ = ExchangeConfig.objects.get_or_create(
                name=data['exchange'].lower(),
                defaults={'api_endpoint': f"https://api.{data['exchange'].lower()}.com"}
            )
            
            # Create bot config
            bot_config = BotConfig.objects.create(
                user_id=user.id,
                exchange=exchange,
                pair=data['pair'],
                api_key=data['api_key'],
                secret_key=data['secret_key'],
                decimal_precision=data['decimal_precision'],
                risk_tolerance=data['risk_tolerance'],
                trade_volume=data['trade_volume'],
                time_interval=data['time_interval'],
                is_active=True
            )
            
            # Start the bot
            success = bot_manager.start_bot(bot_config.id)
            
            if success:
                logger.info(f"Bot {bot_config.id} started successfully")
                return Response({
                    'message': 'Bot started successfully',
                    'bot_id': bot_config.id
                }, status=status.HTTP_201_CREATED)
            else:
                bot_config.is_active = False
                bot_config.save()
                logger.error(f"Failed to start bot {bot_config.id}")
                return Response({
                    'error': 'Failed to start bot',
                    'bot_id': bot_config.id
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BotStopView(APIView):
    """
    API endpoint to stop a trading bot.
    """
    def post(self, request):
        serializer = BotStopSerializer(data=request.data)
        if serializer.is_valid():
            bot_id = serializer.validated_data['bot_id']
            bot = get_object_or_404(BotConfig, id=bot_id)
            
            if not bot.is_active:
                return Response({
                    'message': f'Bot {bot_id} is already stopped'
                }, status=status.HTTP_200_OK)
            
            # Stop the bot
            success = bot_manager.stop_bot(bot_id)
            
            if success:
                bot.is_active = False
                bot.status = 'stopped'
                bot.save()
                logger.info(f"Bot {bot_id} stopped successfully")
                return Response({
                    'message': f'Bot {bot_id} stopped successfully'
                }, status=status.HTTP_200_OK)
            else:
                logger.error(f"Failed to stop bot {bot_id}")
                return Response({
                    'error': f'Failed to stop bot {bot_id}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BotLogView(APIView):
    """
    API endpoint to get bot logs.
    """
    def get(self, request):
        bot_id = request.query_params.get('bot_id')
        limit = int(request.query_params.get('limit', 100))
        
        if bot_id:
            logs = BotLog.objects.filter(bot_config_id=bot_id).order_by('-timestamp')[:limit]
        else:
            logs = BotLog.objects.all().order_by('-timestamp')[:limit]
        
        serializer = BotLogSerializer(logs, many=True)
        return Response(serializer.data)


class BotOrderView(APIView):
    """
    API endpoint to get bot orders.
    """
    def get(self, request):
        bot_id = request.query_params.get('bot_id')
        limit = int(request.query_params.get('limit', 100))
        
        if bot_id:
            logs = Order.objects.filter(bot_config_id=bot_id).order_by('-created_at')[:limit]
        else:
            logs = Order.objects.all().order_by('-created_at')[:limit]
        
        serializer = OrderSerializer(logs, many=True)
        return Response(serializer.data)

class BotWalletBalanceView(APIView):
    """
    API endpoint to get wallet balance for a bot.
    """
    def get(self, request):
        bot_id = request.query_params.get('bot_id')
        
        if not bot_id:
            return Response({
                'error': 'Bot ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
                
        try:
            # Get bot config
            bot_config = get_object_or_404(BotConfig, id=bot_id)
                
            # Get exchange client
            exchange_name = bot_config.exchange.name
            api_key = bot_config.api_key
            secret_key = bot_config.secret_key
                
            if not api_key or not secret_key:
                return Response({
                    'error': 'Missing API credentials'
                }, status=status.HTTP_400_BAD_REQUEST)
                
            logger.info(f"Fetching wallet balance for bot {bot_id} on {exchange_name}")
            exchange_client = get_exchange_client(exchange_name, api_key, secret_key)
                
            # Create event loop for async operation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
                
            try:
                # Initialize client if needed
                if hasattr(exchange_client, '_init_session'):
                    loop.run_until_complete(exchange_client._init_session())
                    
                # Get wallet balance with proper error handling
                try:
                    balances = loop.run_until_complete(exchange_client.get_wallet_balance())
                    
                    # If we got here, we successfully retrieved balances
                    return Response({
                        'bot_id': bot_id,
                        'exchange': exchange_name,
                        'balances': balances
                    })
                except Exception as api_error:
                    logger.error(f"API error fetching wallet balance: {str(api_error)}")
                    logger.error(traceback.format_exc())
                    return Response({
                        'error': f"API error: {str(api_error)}"
                    }, status=status.HTTP_502_BAD_GATEWAY)
            finally:
                # Close any resources
                if hasattr(exchange_client, '_close_session'):
                    try:
                        loop.run_until_complete(exchange_client._close_session())
                    except Exception as e:
                        logger.error(f"Error closing session: {str(e)}")
                loop.close()
                    
        except Exception as e:
            logger.error(f"Error fetching wallet balance: {str(e)}")
            logger.error(traceback.format_exc())
            return Response({
                'error': f"Error fetching wallet balance: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

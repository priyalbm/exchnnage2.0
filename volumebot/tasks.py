from celery import shared_task
from django.db import transaction
from django.utils import timezone
import logging
from .models import BotConfiguration, BotTradeLog, BotPerformanceMetrics
from .utils import ExchangeTradeHandler, PionexTradeHandler

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def execute_bot_trade(self, bot_config_id):
    try:
        # Retrieve bot configuration
        bot_config = BotConfiguration.objects.get(id=bot_config_id)
        
        # Select appropriate trade handler based on exchange
        if bot_config.exchange == 'PIONEX':
            trade_handler = PionexTradeHandler(
                api_key=bot_config.api_key, 
                secret_key=bot_config.secret_key
            )
        else:
            trade_handler = ExchangeTradeHandler(
                api_key=bot_config.api_key, 
                secret_key=bot_config.secret_key,
                exchange=bot_config.exchange
            )
        
        # Perform trade analysis and execution
        with transaction.atomic():
            # Get latest market data
            market_data = trade_handler.get_market_data(bot_config.coin_pair)
            
            # Calculate trade volume based on strategy
            if bot_config.strategy == 'VOLUME_BASED':
                trade_volume = trade_handler.calculate_trade_volume(
                    market_data, 
                    bot_config.volume_percentage
                )
            elif bot_config.strategy == 'PRICE_RANGE':
                # Implement more complex volume calculation based on price range
                trade_volume = _calculate_volume_by_price_range(market_data, bot_config)
            else:
                # Default to basic volume calculation
                trade_volume = trade_handler.calculate_trade_volume(
                    market_data, 
                    bot_config.volume_percentage
                )
            
            # Execute trade
            trade_result = trade_handler.execute_trade(
                coin_pair=bot_config.coin_pair, 
                volume=trade_volume
            )
            
            # Check performance and tolerance
            performance = _check_bot_performance_tolerance(
                bot_config, market_data, trade_result
            )
            
            # Log trade
            trade_log = BotTradeLog.objects.create(
                bot_config=bot_config,
                trade_type=trade_result['type'],
                amount=trade_result['amount'],
                price=trade_result['price'],
                status=trade_result['status']
            )
            
            # Update bot performance
            performance.total_trades += 1
            performance.successful_trades += 1 if trade_result['status'] == 'SUCCESS' else 0
            performance.total_volume += trade_result['amount']
            performance.last_trading_time = timezone.now()
            performance.save()
        
        return trade_log.id
    
    except Exception as e:
        logger.error(f"Bot trade execution failed: {str(e)}")
        return None

def _calculate_volume_by_price_range(market_data, bot_config):
    """
    Calculate trade volume based on price range and market conditions
    """
    current_price = market_data['last_price']
    bid_price = market_data['bid_price']
    ask_price = market_data['ask_price']
    
    # More advanced volume calculation logic
    price_spread = ask_price - bid_price
    relative_position = (current_price - bid_price) / price_spread
    
    # Adjust volume based on price position
    base_volume = bot_config.volume_percentage / 100
    volume_modifier = 1 + (relative_position - 0.5) * 0.5  # Adjust volume based on price position
    
    return base_volume * volume_modifier

def _check_bot_performance_tolerance(bot_config, market_data, trade_result):
    """
    Check bot performance against configured tolerance levels
    """
    performance, _ = BotPerformanceMetrics.objects.get_or_create(
        bot_config=bot_config
    )
    
    # Calculate trade profit/loss
    trade_price = trade_result['price']
    trade_amount = trade_result['amount']
    
    # Track total profit/loss
    if trade_result['type'] == 'BUY':
        trade_profit = 0  # Track on subsequent sell
    else:  # SELL
        # Calculate profit/loss based on last buy price
        # This requires tracking last buy price, which is not implemented here
        trade_profit = (trade_price - performance.last_buy_price) * trade_amount
    
    performance.total_profit += max(trade_profit, 0)
    performance.total_loss += abs(min(trade_profit, 0))
    
    # Check tolerance levels
    profit_percentage = (performance.total_profit / (performance.total_volume or 1)) * 100
    loss_percentage = (performance.total_loss / (performance.total_volume or 1)) * 100
    
    if (profit_percentage >= bot_config.max_profit_percentage or 
        loss_percentage >= bot_config.max_loss_percentage):
        bot_config.is_active = False
        bot_config.save()
    
    return performance

@shared_task
def monitor_active_bots():
    """
    Continuously monitor and execute active bot trades
    """
    active_bots = BotConfiguration.objects.filter(is_active=True)
    
    for bot in active_bots:
        execute_bot_trade.delay(bot.id)
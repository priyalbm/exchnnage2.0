import asyncio
import random
import logging
import traceback
import time
from django.utils import timezone
from channels.db import database_sync_to_async
from ..utils import get_exchange_client
from ..models import BotConfig, Order, ExchangeConfig

# Dictionary to track running bots
RUNNING_BOTS = {}

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add a file handler to save logs
file_handler = logging.FileHandler('trading_bot.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)
logger.setLevel(logging.DEBUG)

async def run_trading_bot(bot_config_id):
    """Start a trading bot"""
    logger.info(f"Starting bot {bot_config_id}")
    
    # Check if bot is already running
    if bot_config_id in RUNNING_BOTS:
        logger.warning(f"Bot {bot_config_id} is already running")
        return {'error': True, 'detail': 'Bot is already running'}
    
    try:
        # Get bot configuration
        bot_config = await get_bot_config_from_db(bot_config_id)
        if not bot_config:
            logger.error(f"Bot {bot_config_id} not found")
            return {'error': True, 'detail': 'Bot not found'}
        
        # Update bot status to running
        await update_bot_status(bot_config, 'running', None)
        
        # Create and start the bot task
        task = asyncio.create_task(simple_trading_bot_loop(bot_config_id))
        RUNNING_BOTS[bot_config_id] = task
        
        # Add callback to handle task completion
        task.add_done_callback(lambda t: handle_task_completion(t, bot_config_id))
        
        logger.info(f"Bot {bot_config_id} started successfully")
        return {'error': False, 'detail': 'Bot started successfully'}
    
    except Exception as e:
        logger.error(f"Error starting bot {bot_config_id}: {str(e)}", exc_info=True)
        return {'error': True, 'detail': f"Failed to start bot: {str(e)}"}

async def stop_bot(bot_config_id):
    """Stop a running trading bot"""
    logger.info(f"Stopping bot {bot_config_id}")
    
    if bot_config_id not in RUNNING_BOTS:
        logger.info(f"Bot {bot_config_id} is not running")
        return {'error': False, 'detail': 'Bot is not running'}
    
    try:
        # Cancel the task
        task = RUNNING_BOTS[bot_config_id]
        task.cancel()
        
        # Update bot status
        bot_config = await get_bot_config_from_db(bot_config_id)
        if bot_config:
            await update_bot_status(bot_config, 'stopped', None)
        
        logger.info(f"Bot {bot_config_id} stopped successfully")
        return {'error': False, 'detail': 'Bot stopped successfully'}
    
    except Exception as e:
        logger.error(f"Error stopping bot {bot_config_id}: {str(e)}", exc_info=True)
        return {'error': True, 'detail': f"Failed to stop bot: {str(e)}"}

async def simple_trading_bot_loop(bot_config_id):
    """Simplified trading bot loop"""
    logger.info(f"Starting simple trading bot loop for bot {bot_config_id}")
    
    try:
        # Get bot configuration
        bot_config = await get_bot_config_from_db(bot_config_id)
        if not bot_config:
            logger.error(f"Bot {bot_config_id} not found")
            return
        
        # Initialize exchange client
        client = initialize_exchange_client(bot_config)
        if not client:
            await update_bot_status(bot_config, 'error', "Failed to initialize exchange client")
            return
        
        logger.info(f"Exchange client initialized for {bot_config.exchange_config.exchange.code}")
        
        # Main trading loop
        while True:
            try:
                # Check if task is cancelled
                if asyncio.current_task().cancelled():
                    logger.info(f"Bot {bot_config_id} task cancelled")
                    break
                
                # Refresh bot config
                bot_config = await get_bot_config_from_db(bot_config_id)
                if not bot_config:
                    logger.error(f"Bot {bot_config_id} not found during refresh")
                    break
                
                # Check bot status
                if bot_config.status != 'running':
                    logger.info(f"Bot {bot_config_id} status is {bot_config.status}, stopping loop")
                    break
                
                # Check remaining volume
                if bot_config.remaining_volume <= 0:
                    logger.info(f"Bot {bot_config_id} has no remaining volume")
                    await update_bot_status(bot_config, 'completed', "Trading volume completed")
                    break
                
                # Get market data
                ticker_data = get_ticker_data(client, bot_config.symbol)
                if not ticker_data:
                    logger.warning(f"Failed to get ticker data for {bot_config.symbol}, retrying...")
                    await asyncio.sleep(5)
                    continue
                
                # Get order book
                order_book = get_order_book(client, bot_config.symbol)
                if not order_book:
                    logger.warning(f"Failed to get order book for {bot_config.symbol}, retrying...")
                    await asyncio.sleep(5)
                    continue
                
                # Calculate price and quantity
                price, quantity = calculate_order_params(bot_config, order_book)
                if not price or not quantity:
                    logger.warning("Failed to calculate order parameters, retrying...")
                    await asyncio.sleep(5)
                    continue
                
                # Place order
                success = await place_order(client, bot_config, price, quantity)
                if success:
                    # Update bot statistics
                    await update_bot_after_order(bot_config, quantity)
                    logger.info(f"Order placed successfully: {quantity} @ {price}")
                
                # Update last run time
                await update_last_run_time(bot_config)
                
                # Sleep before next iteration
                await asyncio.sleep(bot_config.time_interval)
            
            except asyncio.CancelledError:
                logger.info(f"Bot {bot_config_id} task cancelled in loop")
                raise
            
            except Exception as e:
                logger.error(f"Error in trading loop: {str(e)}", exc_info=True)
                await asyncio.sleep(10)  # Sleep and retry
    
    except asyncio.CancelledError:
        logger.info(f"Bot {bot_config_id} task cancelled")
        bot_config = await get_bot_config_from_db(bot_config_id)
        if bot_config:
            await update_bot_status(bot_config, 'stopped', "Bot was stopped")
    
    except Exception as e:
        logger.error(f"Fatal error in bot {bot_config_id}: {str(e)}", exc_info=True)
        bot_config = await get_bot_config_from_db(bot_config_id)
        if bot_config:
            await update_bot_status(bot_config, 'error', f"Fatal error: {str(e)}")
    
    finally:
        # Clean up
        if bot_config_id in RUNNING_BOTS:
            RUNNING_BOTS.pop(bot_config_id, None)
        logger.info(f"Bot {bot_config_id} loop ended")

# Helper functions

@database_sync_to_async
def get_bot_config_from_db(bot_id):
    """Get bot configuration from database"""
    try:
        from ..models import BotConfig
        bot = BotConfig.objects.select_related(
            'exchange_config', 
            'exchange_config__exchange',
            'user'
        ).get(id=bot_id)
        return bot
    except Exception as e:
        logger.error(f"Error getting bot config: {str(e)}", exc_info=True)
        return None

@database_sync_to_async
def update_bot_status(bot_config, status, message):
    """Update bot status in database"""
    try:
        bot_config.status = status
        bot_config.error_message = message
        bot_config.last_run = timezone.now()
        bot_config.save()
        logger.info(f"Updated bot {bot_config.id} status to {status}")
        return True
    except Exception as e:
        logger.error(f"Error updating bot status: {str(e)}", exc_info=True)
        return False

@database_sync_to_async
def update_last_run_time(bot_config):
    """Update bot last run time"""
    try:
        bot_config.last_run = timezone.now()
        bot_config.save(update_fields=['last_run'])
        return True
    except Exception as e:
        logger.error(f"Error updating last run time: {str(e)}", exc_info=True)
        return False

@database_sync_to_async
def update_bot_after_order(bot_config, quantity):
    """Update bot statistics after successful order"""
    try:
        bot_config.total_orders += 1
        bot_config.successful_orders += 1
        bot_config.remaining_volume -= quantity
        bot_config.completed_volume += quantity
        bot_config.save()
        logger.info(f"Updated bot {bot_config.id} statistics after order")
        return True
    except Exception as e:
        logger.error(f"Error updating bot statistics: {str(e)}", exc_info=True)
        return False

@database_sync_to_async
def create_order_record(bot_config, symbol, order_data, side, price, quantity):
    """Create order record in database"""
    try:
        from ..models import Order
        order = Order(
            user=bot_config.user,
            bot_config=bot_config,
            exchange_config=bot_config.exchange_config,
            symbol=symbol,
            order_id=order_data.get('orderId', ''),
            exchange_order_id=order_data.get('orderId', ''),
            side=side,
            order_type='LIMIT',
            price=price,
            quantity=quantity,
            status='PENDING'
        )
        order.save()
        logger.info(f"Created order record: {order.id}")
        return order
    except Exception as e:
        logger.error(f"Error creating order record: {str(e)}", exc_info=True)
        return None

def initialize_exchange_client(bot_config):
    """Initialize exchange client with error handling"""
    try:
        # Check if this is a test configuration
        is_testing = (
            bot_config.exchange_config.api_key == "DUMMY_API_KEY" or 
            "DUMMY" in bot_config.exchange_config.api_key or
            "TEST" in bot_config.exchange_config.api_key
        )
        
        if is_testing:
            logger.info("Using mock exchange client for testing")
            from ..exchange_clients.base import ExchangeClient
            
            class MockExchangeClient(ExchangeClient):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    
                def get_trading_pairs(self):
                    return {
                        "error": False,
                        "data": [
                            {"symbol": bot_config.symbol, "baseCurrency": "BTC", "quoteCurrency": "USDT", 
                             "basePrecision": 8, "quotePrecision": 8}
                        ]
                    }
                    
                def get_ticker(self, symbol):
                    return {
                        "error": False,
                        "data": {
                            "symbol": symbol,
                            "lastPrice": 50000.0,
                            "bidPrice": 49995.0,
                            "askPrice": 50005.0,
                            "volume": 100.0,
                            "timestamp": int(time.time() * 1000)
                        }
                    }
                    
                def get_order_book(self, symbol):
                    return {
                        "error": False,
                        "data": {
                            "symbol": symbol,
                            "bids": [[49995.0, 1.0], [49990.0, 2.0], [49980.0, 3.0]],
                            "asks": [[50005.0, 1.0], [50010.0, 2.0], [50020.0, 3.0]],
                            "timestamp": int(time.time() * 1000)
                        }
                    }
                    
                def get_balance(self):
                    return {
                        "error": False,
                        "data": {
                            "BTC": {"available": 1.0, "locked": 0.0},
                            "USDT": {"available": 50000.0, "locked": 0.0}
                        }
                    }
                    
                def create_order(self, symbol, side, order_type, quantity, price=None):
                    order_id = f"test-order-{int(time.time())}"
                    return {
                        "error": False,
                        "data": {
                            "orderId": order_id,
                            "symbol": symbol,
                            "side": side,
                            "type": order_type,
                            "price": price,
                            "quantity": quantity,
                            "status": "FILLED",
                            "timestamp": int(time.time() * 1000)
                        }
                    }
            
            return MockExchangeClient(api_key="test", api_secret="test")
        else:
            # Get real exchange client
            from ..utils import get_exchange_client
            
            # Log API credentials (masked)
            api_key = bot_config.exchange_config.api_key
            masked_key = api_key[:4] + "****" + api_key[-4:] if len(api_key) > 8 else "****"
            logger.info(f"Using API key: {masked_key}")
            
            base_url = bot_config.exchange_config.base_url or bot_config.exchange_config.exchange.base_url
            
            client = get_exchange_client(
                exchange_code=bot_config.exchange_config.exchange.code,
                api_key=bot_config.exchange_config.api_key,
                api_secret=bot_config.exchange_config.api_secret,
                base_url=base_url
            )
            
            # Test client with a simple API call
            if client:
                try:
                    # Try to get trading pairs as a test
                    result = client.get_trading_pairs()
                    if result and not result.get('error', False):
                        logger.info(f"Exchange client initialized and tested successfully")
                        return client
                    else:
                        error_msg = result.get('detail', 'Unknown error') if result else 'Null response'
                        logger.error(f"Exchange client test failed: {error_msg}")
                        return None
                except Exception as e:
                    logger.error(f"Error testing exchange client: {str(e)}", exc_info=True)
                    return None
            else:
                logger.error(f"Failed to initialize exchange client")
                return None
    
    except Exception as e:
        logger.error(f"Error initializing exchange client: {str(e)}", exc_info=True)
        return None

def get_ticker_data(client, symbol):
    """Get ticker data with error handling"""
    try:
        response = client.get_ticker(symbol)
        if response and not response.get('error', False):
            return response.get('data', {})
        else:
            error_msg = response.get('detail', 'Unknown error') if response else 'Null response'
            logger.error(f"Error getting ticker: {error_msg}")
            return None
    except Exception as e:
        logger.error(f"Exception getting ticker: {str(e)}", exc_info=True)
        return None

def get_order_book(client, symbol):
    """Get order book with error handling"""
    try:
        response = client.get_order_book(symbol)
        if response and not response.get('error', False):
            return response.get('data', {})
        else:
            error_msg = response.get('detail', 'Unknown error') if response else 'Null response'
            logger.error(f"Error getting order book: {error_msg}")
            return None
    except Exception as e:
        logger.error(f"Exception getting order book: {str(e)}", exc_info=True)
        return None

def calculate_order_params(bot_config, order_book):
    """Calculate order price and quantity"""
    try:
        # Extract bids and asks
        bids = order_book.get('bids', [])
        asks = order_book.get('asks', [])
        
        if not bids or not asks:
            logger.warning("Empty bids or asks in order book")
            return None, None
        
        # Get highest bid and lowest ask
        bid_entry = bids[0]
        ask_entry = asks[0]
        
        # Handle different formats
        if isinstance(bid_entry, list):
            highest_bid = float(bid_entry[0])
            lowest_ask = float(ask_entry[0])
        elif isinstance(bid_entry, dict) and 'price' in bid_entry:
            highest_bid = float(bid_entry['price'])
            lowest_ask = float(ask_entry['price'])
        else:
            # Fallback
            highest_bid = float(bid_entry[0] if isinstance(bid_entry, list) else next(iter(bid_entry.values())))
            lowest_ask = float(ask_entry[0] if isinstance(ask_entry, list) else next(iter(ask_entry.values())))
        
        # Calculate price (random within spread)
        price = round(
            random.uniform(highest_bid, lowest_ask),
            bot_config.decimal_places
        )
        
        # Calculate quantity
        quantity = min(bot_config.per_order_volume, bot_config.remaining_volume)
        quantity = round(quantity, bot_config.quantity_decimal_places)
        
        return price, quantity
    
    except Exception as e:
        logger.error(f"Error calculating order parameters: {str(e)}", exc_info=True)
        return None, None

async def place_order(client, bot_config, price, quantity):
    """Place order with error handling"""
    try:
        # Place buy order
        buy_response = client.create_order(
            symbol=bot_config.symbol,
            side='BUY',
            order_type='LIMIT',
            quantity=quantity,
            price=price
        )
        
        if not buy_response or buy_response.get('error', False):
            error_msg = buy_response.get('detail', 'Unknown error') if buy_response else 'Null response'
            logger.error(f"Error placing order: {error_msg}")
            return False
        
        # Create order record
        await create_order_record(
            bot_config,
            bot_config.symbol,
            buy_response['data'],
            'BUY',
            price,
            quantity
        )
        
        return True
    
    except Exception as e:
        logger.error(f"Exception placing order: {str(e)}", exc_info=True)
        return False

def handle_task_completion(task, bot_config_id):
    """Handle task completion"""
    try:
        # Remove from running bots
        if bot_config_id in RUNNING_BOTS:
            RUNNING_BOTS.pop(bot_config_id, None)
        
        # Check for exceptions
        if task.cancelled():
            logger.info(f"Bot {bot_config_id} task was cancelled")
        elif task.exception():
            logger.error(f"Bot {bot_config_id} task failed with exception: {task.exception()}")
        else:
            logger.info(f"Bot {bot_config_id} task completed normally")
    
    except Exception as e:
        logger.error(f"Error handling task completion: {str(e)}", exc_info=True)

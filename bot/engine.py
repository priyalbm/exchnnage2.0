import asyncio
import logging
import random
import time
from decimal import Decimal, getcontext
import threading
from django.db import transaction
from django.utils import timezone

from .models import BotConfig, BotLog, Order
from .exchanges import get_exchange_client

# Set up logger
logger = logging.getLogger('bot')

# Set decimal precision
getcontext().prec = 28


class TradingBot:
    """
    Trading bot implementation for a specific bot configuration.
    Handles the trading loop and strategy.
    """
    def __init__(self, bot_config_id):
        """
        Initialize the trading bot with a configuration.
        
        Args:
            bot_config_id (int): ID of the BotConfig
        """
        self.bot_config_id = bot_config_id
        self.bot_config = None
        self.exchange_client = None
        self.running = False
        self.task = None
        self.stop_event = asyncio.Event()
    
    async def initialize(self):
        """
        Initialize the bot with configuration and exchange client.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get the bot configuration - run in a thread to avoid async context issues
            self.bot_config = await asyncio.to_thread(
                self._get_bot_config
            )
            
            # Create exchange client
            self.exchange_client = get_exchange_client(
                self.bot_config.exchange.name,
                self.bot_config.api_key,
                self.bot_config.secret_key
            )
            
            # Log initialization
            await self.log("INFO", f"Bot initialized for {self.bot_config.exchange.name}:{self.bot_config.pair}")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing bot {self.bot_config_id}: {str(e)}")
            await self.log("ERROR", f"Initialization error: {str(e)}")
            return False
    
    def _get_bot_config(self):
        """Get bot configuration from database - runs in sync context"""
        return BotConfig.objects.get(id=self.bot_config_id)
    
    async def log(self, level, message):
        """
        Log a message to the database.
        
        Args:
            level (str): Log level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
            message (str): Log message
        """
        try:
            await asyncio.to_thread(
                BotLog.objects.create,
                bot_config_id=self.bot_config_id,
                level=level,
                message=message
            )
        except Exception as e:
            logger.error(f"Error logging message: {str(e)}")
    
    async def start(self):
        """
        Start the trading bot.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        if self.running:
            await self.log("WARNING", "Bot is already running")
            return False
        
        success = await self.initialize()
        if not success:
            return False
        
        self.running = True
        self.stop_event.clear()
        self.task = asyncio.create_task(self.run_trading_loop())
        
        await self.log("INFO", "Bot started")
        return True
    
    async def stop(self):
        """
        Stop the trading bot.
        
        Returns:
            bool: True if stopped successfully, False otherwise
        """
        if not self.running:
            await self.log("WARNING", "Bot is not running")
            return False
        
        self.running = False
        self.stop_event.set()
        
        if self.task:
            try:
                await asyncio.wait_for(self.task, timeout=10)
            except asyncio.TimeoutError:
                # If the task doesn't complete in time, cancel it
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass
            self.task = None
        
        await self.log("INFO", "Bot stopped")
        return True
    
    async def run_trading_loop(self):
        """
        Main trading loop that implements the trading strategy.
        """
        await self.log("INFO", f"Starting trading loop with interval: {self.bot_config.time_interval}s")
        
        try:
            while self.running and not self.stop_event.is_set():
                try:
                    # Step 1: Fetch wallet balance
                    await self.log("DEBUG", "Fetching wallet balance")
                    wallet = await self.exchange_client.get_wallet_balance()
                    
                    # Get the quote asset (e.g., USDT from BTC_USDT)
                    quote_asset = self.bot_config.pair.split('_')[1]
                    
                    if quote_asset not in wallet:
                        await self.log("ERROR", f"Quote asset {quote_asset} not found in wallet")
                        self.running = False
                        break
                    
                    quote_balance = Decimal(str(wallet[quote_asset]['free']))
                    await self.log("INFO", f"Available balance: {quote_balance} {quote_asset}")
                    
                    # Step 2: Get order book and ticker data
                    await self.log("DEBUG", "Fetching order book")
                    order_book = await self.exchange_client.get_order_book(self.bot_config.pair)
                    
                    await self.log("DEBUG", "Fetching 24h ticker")
                    ticker = await self.exchange_client.get_24h_ticker(self.bot_config.pair)
                    
                    # Get the current price from ticker
                    current_price = Decimal(str(ticker['last_price']))
                    
                    # Step 3: Calculate trade volume and check balance
                    trade_amount = self.bot_config.trade_volume * current_price
                    await self.log("INFO", f"Trade amount: {trade_amount} {quote_asset}")
                    
                    if trade_amount > quote_balance:
                        await self.log("WARNING", f"Insufficient balance: {quote_balance} < {trade_amount}")
                        self.running = False
                        break
                    
                    # Step 4: Market depth analysis
                    is_bullish = await self.analyze_market_depth(order_book)
                    await self.log("INFO", f"Market analysis: {'Bullish' if is_bullish else 'Bearish'}")
                    
                    # Step 5: Calculate spread
                    await self.log("DEBUG", "Re-fetching order book for spread calculation")
                    order_book = await self.exchange_client.get_order_book(self.bot_config.pair)
                    
                    # Calculate spread metrics
                    max_buy_price = Decimal(str(order_book['bids'][0][0]))
                    min_sell_price = Decimal(str(order_book['asks'][0][0]))
                    
                    spread = min_sell_price - max_buy_price
                    mid_price = (min_sell_price + max_buy_price) / 2
                    spread_percentage = (spread / mid_price) * 100
                    
                    await self.log("INFO", (
                        f"Spread metrics: Max Buy: {max_buy_price}, Min Sell: {min_sell_price}, "
                        f"Spread: {spread}, Mid Price: {mid_price}, Spread %: {spread_percentage}"
                    ))
                    
                    # Check if spread is favorable
                    risk_tolerance = Decimal(str(self.bot_config.risk_tolerance))
                    if spread_percentage <= risk_tolerance:
                        await self.log("INFO", f"Spread percentage {spread_percentage}% is below risk tolerance {risk_tolerance}%")
                        await asyncio.sleep(self.bot_config.time_interval)
                        continue
                    
                    # Step 6: Generate a random trade price
                    # Convert to strings to avoid float precision issues
                    max_buy_str = str(max_buy_price)
                    min_sell_str = str(min_sell_price)
                    
                    # Random value between buy and sell price
                    price_range = float(min_sell_str) - float(max_buy_str)
                    random_offset = random.random() * price_range
                    trade_price = Decimal(max_buy_str) + Decimal(str(random_offset))
                    
                    # Round to appropriate decimal places
                    decimal_precision = self.bot_config.decimal_precision
                    trade_price = trade_price.quantize(Decimal('0.' + '0' * decimal_precision))
                    
                    await self.log("INFO", f"Generated trade price: {trade_price}")
                    
                    # Step 7: Place orders
                    # Calculate the volume based on trade_amount and trade_price
                    trade_volume = self.bot_config.trade_volume
                    
                    # Place a sell order
                    await self.log("INFO", f"Placing sell order: {trade_volume} @ {trade_price}")
                    sell_order = await self.exchange_client.place_order(
                        'sell', self.bot_config.pair, float(trade_volume), float(trade_price)
                    )
                    
                    # Save the sell order to the database
                    await asyncio.to_thread(
                        self.save_order,
                        'SELL',
                        sell_order['order_id'],
                        sell_order['price'],
                        sell_order['orig_qty']
                    )
                    
                    # Place a buy order slightly below the sell price
                    buy_price = trade_price * Decimal('0.999')  # 0.1% lower
                    buy_price = buy_price.quantize(Decimal('0.' + '0' * decimal_precision))
                    
                    await self.log("INFO", f"Placing buy order: {trade_volume} @ {buy_price}")
                    buy_order = await self.exchange_client.place_order(
                        'buy', self.bot_config.pair, float(trade_volume), float(buy_price)
                    )
                    
                    # Save the buy order to the database
                    await asyncio.to_thread(
                        self.save_order,
                        'BUY',
                        buy_order['order_id'],
                        buy_order['price'],
                        buy_order['orig_qty']
                    )
                    
                except Exception as e:
                    await self.log("ERROR", f"Error in trading loop: {str(e)}")
                    # If there's an error, sleep and try again
                    await asyncio.sleep(self.bot_config.time_interval)
                
                # Wait for the next iteration
                await asyncio.sleep(self.bot_config.time_interval)
                
        except asyncio.CancelledError:
            await self.log("INFO", "Trading loop cancelled")
            raise
        except Exception as e:
            await self.log("CRITICAL", f"Unhandled exception in trading loop: {str(e)}")
        finally:
            # Ensure bot is marked as stopped in the database
            await asyncio.to_thread(self.mark_bot_stopped)
    
    async def analyze_market_depth(self, order_book):
        """
        Analyze market depth to determine if the market is bullish or bearish.
        
        Args:
            order_book (dict): Order book with bids and asks
            
        Returns:
            bool: True if bullish, False if bearish
        """
        # Calculate total volume of bids and asks
        bid_volume = sum(bid[1] for bid in order_book['bids'])
        ask_volume = sum(ask[1] for ask in order_book['asks'])
        
        # If bid volume is greater than ask volume, market is bullish
        return bid_volume > ask_volume
    
    def save_order(self, order_type, order_id, price, volume):
        """
        Save an order to the database.
        
        Args:
            order_type (str): 'BUY' or 'SELL'
            order_id (str): Exchange order ID
            price (float): Order price
            volume (float): Order volume
        """
        try:
            with transaction.atomic():
                Order.objects.create(
                    bot_config_id=self.bot_config_id,
                    order_id=str(order_id),
                    pair=self.bot_config.pair,
                    order_type=order_type,
                    price=price,
                    volume=volume,
                    status='OPEN'
                )
        except Exception as e:
            logger.error(f"Error saving order: {str(e)}")
    
    def mark_bot_stopped(self):
        """Mark the bot as stopped in the database"""
        try:
            with transaction.atomic():
                bot = BotConfig.objects.get(id=self.bot_config_id)
                bot.is_active = False
                bot.save()
        except Exception as e:
            logger.error(f"Error marking bot as stopped: {str(e)}")


class BotManager:
    """
    Manager class to handle multiple trading bots.
    """
    def __init__(self):
        self.bots = {}
        self.loop = None
    
    def _get_event_loop(self):
        """
        Get the event loop for the current thread.
        
        Returns:
            asyncio.AbstractEventLoop: The event loop
        """
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            # If there's no event loop in this thread, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop
    
    def start_bot(self, bot_id):
        """
        Start a trading bot with the given configuration ID.
        
        Args:
            bot_id (int): The bot configuration ID
            
        Returns:
            bool: True if started successfully, False otherwise
        """
        if bot_id in self.bots:
            logger.warning(f"Bot {bot_id} is already running")
            return False
        
        try:
            # Create a new bot instance
            bot = TradingBot(bot_id)
            
            # Make sure we have an event loop running in a background thread
            if self.loop is None:
                # Start the event loop in a background thread first
                self.start_event_loop()
            
            # Start the bot
            future = asyncio.run_coroutine_threadsafe(bot.start(), self.loop)
            result = future.result(timeout=30)  # Wait for up to 30 seconds for the bot to start
            
            if result:
                self.bots[bot_id] = bot
                logger.info(f"Bot {bot_id} started successfully")
                return True
            else:
                logger.error(f"Failed to start bot {bot_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error starting bot {bot_id}: {str(e)}")
            return False
    
    def stop_bot(self, bot_id):
        """
        Stop a trading bot with the given configuration ID.
        
        Args:
            bot_id (int): The bot configuration ID
            
        Returns:
            bool: True if stopped successfully, False otherwise
        """
        if bot_id not in self.bots:
            logger.warning(f"Bot {bot_id} is not running")
            return False
        
        try:
            bot = self.bots[bot_id]
            
            # Stop the bot
            future = asyncio.run_coroutine_threadsafe(bot.stop(), self.loop)
            result = future.result(timeout=30)  # Wait for up to 30 seconds for the bot to stop
            
            if result:
                del self.bots[bot_id]
                logger.info(f"Bot {bot_id} stopped successfully")
                return True
            else:
                logger.error(f"Failed to stop bot {bot_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error stopping bot {bot_id}: {str(e)}")
            return False
    
    def start_event_loop(self):
        """Start the event loop in a separate thread."""
        if self.loop is None:
            self.loop = asyncio.new_event_loop()
            
            def run_event_loop():
                asyncio.set_event_loop(self.loop)
                self.loop.run_forever()
            
            # Start loop in a daemon thread
            thread = threading.Thread(target=run_event_loop, daemon=True)
            thread.start()
    
    def stop_all_bots(self):
        """Stop all running bots."""
        for bot_id in list(self.bots.keys()):
            self.stop_bot(bot_id)
    
    def shutdown(self):
        """Shutdown the bot manager and stop all bots."""
        self.stop_all_bots()
        
        if self.loop is not None and self.loop.is_running():
            # Schedule a call to stop the loop
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.loop = None

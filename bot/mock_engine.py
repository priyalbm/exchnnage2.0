"""
Diagnostic version of the mock trading bot engine for Django.
This version includes extra debug logging to identify issues.
"""

import threading
import time
import logging
import random
import traceback
from django.db import transaction
from django.db.models import Sum
from django.db import models

# Set up logger - use a file handler to ensure logs are captured
logger = logging.getLogger('bot')
logger.setLevel(logging.DEBUG)

# Add this line to your main Django settings.py
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class MockTradingBot:
    """
    Diagnostic version of the trading bot with extensive logging.
    """
    def __init__(self, bot_id):
        """Initialize the bot with its ID"""
        self.bot_id = bot_id
        self.running = False
        self.thread = None
        self.stop_event = threading.Event()
        logger.debug(f"Bot {bot_id} initialized")
    
    def start(self):
        """Start the bot in a separate thread"""
        logger.debug(f"Attempting to start bot {self.bot_id}")
        if self.running:
            logger.warning(f"Bot {self.bot_id} is already running")
            return False
        
        try:
            # Retrieve the bot configuration
            logger.debug(f"Retrieving configuration for bot {self.bot_id}")
            from .models import BotConfig
            bot = BotConfig.objects.get(id=self.bot_id)
            logger.debug(f"Found bot configuration: {bot.id}, pair: {bot.pair}")
            
            # Create a new thread to run the bot
            logger.debug(f"Creating thread for bot {self.bot_id}")
            self.thread = threading.Thread(target=self._run_bot)
            self.thread.daemon = True  # Thread will exit when the program exits
            
            # Mark the bot as active in the database
            logger.debug(f"Marking bot {self.bot_id} as active")
            bot.is_active = True
            bot.save()
            logger.debug(f"Bot {self.bot_id} saved as active in database")
            
            # Start the thread
            logger.debug(f"Starting thread for bot {self.bot_id}")
            self.running = True
            self.stop_event.clear()
            self.thread.start()
            
            # Log the start event
            logger.debug(f"Logging start event for bot {self.bot_id}")
            self._log("INFO", f"Bot started with configuration: {bot.pair}, interval: {bot.time_interval}s")
            
            logger.debug(f"Bot {self.bot_id} started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error starting bot {self.bot_id}: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def stop(self):
        """Stop the bot"""
        logger.debug(f"Attempting to stop bot {self.bot_id}")
        if not self.running:
            logger.warning(f"Bot {self.bot_id} is not running")
            return False
        
        try:
            # Signal the thread to stop
            logger.debug(f"Setting stop event for bot {self.bot_id}")
            self.stop_event.set()
            self.running = False
            
            # Wait for the thread to finish
            if self.thread and self.thread.is_alive():
                logger.debug(f"Waiting for bot {self.bot_id} thread to finish")
                self.thread.join(timeout=5)
            
            # Mark the bot as inactive in the database
            logger.debug(f"Marking bot {self.bot_id} as stopped")
            self._mark_stopped()
            
            # Log the stop event
            logger.debug(f"Logging stop event for bot {self.bot_id}")
            self._log("INFO", "Bot stopped")
            
            logger.debug(f"Bot {self.bot_id} stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping bot {self.bot_id}: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _run_bot(self):
        """Main bot loop that runs in a separate thread"""
        logger.debug(f"Bot {self.bot_id} thread started")
        try:
            # Get the bot configuration
            from .models import BotConfig
            logger.debug(f"Retrieving configuration for bot {self.bot_id} in thread")
            bot = BotConfig.objects.get(id=self.bot_id)
            
            # Log initialization
            logger.debug(f"Logging initialization for bot {self.bot_id}")
            self._log("INFO", f"Bot loop started for {bot.exchange.name}:{bot.pair}")
            
            # Mock trading loop
            cycle_count = 0
            logger.debug(f"Starting trading loop for bot {self.bot_id}")
            while not self.stop_event.is_set():
                try:
                    # Print debug information
                    cycle_count += 1
                    logger.debug(f"Bot {self.bot_id} - Trading cycle {cycle_count} starting")
                    
                    # Simulate some trading activity
                    self._simulate_trading(bot)
                    
                    # Sleep for the configured interval
                    logger.debug(f"Bot {self.bot_id} - Sleeping for {bot.time_interval} seconds")
                    time.sleep(bot.time_interval)
                    
                except Exception as e:
                    logger.error(f"Error in trading loop: {str(e)}")
                    logger.error(traceback.format_exc())
                    self._log("ERROR", f"Error in trading loop: {str(e)}")
                    time.sleep(bot.time_interval)
            
            logger.debug(f"Bot {self.bot_id} - Trading loop ended")
            
        except Exception as e:
            logger.error(f"Unhandled exception in bot thread: {str(e)}")
            logger.error(traceback.format_exc())
            self._log("CRITICAL", f"Unhandled exception: {str(e)}")
        finally:
            # Ensure the bot is marked as stopped
            logger.debug(f"Ensuring bot {self.bot_id} is marked as stopped")
            self._mark_stopped()
    
    def _simulate_trading(self, bot):
        """Simulate trading activity following the specified steps with detailed logging"""
        logger.debug(f"Bot {self.bot_id} - Starting trading simulation")
        try:
            # Step 1: Fetch wallet balance (simulated)
            logger.debug(f"Bot {self.bot_id} - Step 1: Parsing trading pair and fetching balance")
            # Handle different pair formats (BTC/USDT, BTCUSDT, BTC-USDT)
            try:
                if '/' in bot.pair:
                    base_currency, quote_currency = bot.pair.split('/')
                elif '-' in bot.pair:
                    base_currency, quote_currency = bot.pair.split('-')
                else:
                    # Try to split based on common quote currencies
                    for quote in ['USDT', 'USD', 'BTC', 'ETH', 'BUSD', 'USDC']:
                        if bot.pair.endswith(quote):
                            base_currency = bot.pair[:-len(quote)]
                            quote_currency = quote
                            break
                    else:
                        # Default fallback - assume last 4 characters are quote currency
                        base_currency = bot.pair[:-4]
                        quote_currency = bot.pair[-4:]
                
                logger.debug(f"Bot {self.bot_id} - Parsed pair as {base_currency}/{quote_currency}")
                self._log("INFO", f"Parsed trading pair: {base_currency}/{quote_currency}")
            except Exception as e:
                logger.error(f"Failed to parse trading pair '{bot.pair}': {str(e)}")
                logger.error(traceback.format_exc())
                self._log("ERROR", f"Failed to parse trading pair '{bot.pair}': {str(e)}")
                # Set default values to continue
                base_currency = "BTC"
                quote_currency = "USDT"
                logger.debug(f"Bot {self.bot_id} - Using default pair {base_currency}/{quote_currency}")
                
            base_balance = random.uniform(0.1, 2.0)  # Simulated balance of base currency (e.g., BTC)
            quote_balance = random.uniform(5000.0, 20000.0)  # Simulated balance of quote currency (e.g., USDT)
            
            logger.debug(f"Bot {self.bot_id} - Generated balances: {base_balance:.8f} {base_currency}, {quote_balance:.2f} {quote_currency}")
            self._log("INFO", f"Wallet balance: {base_balance:.8f} {base_currency}, {quote_balance:.2f} {quote_currency}")
            
            # Step 2: Get order book data (simulated)
            logger.debug(f"Bot {self.bot_id} - Step 2: Generating order book")
            base_price = 50000.0  # Example base price for BTC
            price_variation = random.uniform(-500.0, 500.0)
            current_price = base_price + price_variation
            
            # Simulate an order book with bids and asks
            best_bid = current_price * 0.995  # 0.5% below current price
            best_ask = current_price * 1.005  # 0.5% above current price
            
            logger.debug(f"Bot {self.bot_id} - Generated price: ${current_price:.2f}, Bid: ${best_bid:.2f}, Ask: ${best_ask:.2f}")
            self._log("INFO", f"Current price: ${current_price:.2f}, Bid: ${best_bid:.2f}, Ask: ${best_ask:.2f}")
            
            # Step 3: Calculate Trade Value = Volume * Price
            logger.debug(f"Bot {self.bot_id} - Step 3: Calculating trade value")
            trade_volume = float(bot.trade_volume)
            logger.debug(f"Bot {self.bot_id} - Trade volume from config: {trade_volume}")
            trade_value = trade_volume * current_price
            logger.debug(f"Bot {self.bot_id} - Calculated trade value: ${trade_value:.2f}")
            
            # If trade value > wallet balance, log warning but continue to try both orders
            if trade_value > quote_balance:
                logger.debug(f"Bot {self.bot_id} - Insufficient total balance: ${trade_value:.2f} > ${quote_balance:.2f}")
                self._log("WARNING", f"Insufficient total balance: Trade value ${trade_value:.2f} > Available ${quote_balance:.2f}")
                # Check if balance is too low to continue trading - auto-stop the bot
                logger.debug(f"Bot {self.bot_id} - Insufficient balance to continue trading. Stopping bot.")
                self._log("WARNING", f"Insufficient balance to continue trading. Auto-stopping bot.")
                # Set a flag to stop the bot after this cycle
                self.stop_event.set()
            else:
                logger.debug(f"Bot {self.bot_id} - Sufficient balance for trading")
                self._log("INFO", f"Trade value: ${trade_value:.2f} < Available ${quote_balance:.2f} - Proceeding")
            
            # Step 4: Analyze market depth to determine if bullish or bearish
            logger.debug(f"Bot {self.bot_id} - Step 4: Analyzing market sentiment")
            is_bullish = random.choice([True, False])
            market_sentiment = "bullish" if is_bullish else "bearish"
            logger.debug(f"Bot {self.bot_id} - Market sentiment: {market_sentiment}")
            self._log("INFO", f"Market sentiment: {market_sentiment}")
            
            # Step 5: Calculate spread
            logger.debug(f"Bot {self.bot_id} - Step 5: Calculating spread")
            spread = best_ask - best_bid
            mid_price = (best_ask + best_bid) / 2
            spread_percentage = (spread / mid_price) * 100
            
            logger.debug(f"Bot {self.bot_id} - Spread: ${spread:.2f}, Spread %: {spread_percentage:.2f}%")
            self._log("INFO", f"Spread: ${spread:.2f}, Spread %: {spread_percentage:.2f}%")
            
            # Check if spread % > risk tolerance
            try:
                risk_tolerance = float(bot.risk_tolerance)
                logger.debug(f"Bot {self.bot_id} - Risk tolerance from config: {risk_tolerance}%")
                
                if spread_percentage <= risk_tolerance:
                    logger.debug(f"Bot {self.bot_id} - Spread too small, waiting for next cycle")
                    self._log("INFO", f"Spread % {spread_percentage:.2f}% <= Risk tolerance {risk_tolerance}%. Waiting...")
                    return
            except Exception as e:
                logger.error(f"Error checking risk tolerance: {str(e)}")
                logger.error(traceback.format_exc())
                self._log("ERROR", f"Error checking risk tolerance: {str(e)}")
            
            # Step 6: Generate a random number between Buy and Sell
            logger.debug(f"Bot {self.bot_id} - Step 6: Generating trade price")
            # Use a weighted random number to favor buying when bullish and selling when bearish
            if is_bullish:
                # For bullish markets, place trade price closer to ask
                weight = random.uniform(0.6, 0.9)
            else:
                # For bearish markets, place trade price closer to bid
                weight = random.uniform(0.1, 0.4)
            
            trade_price = best_bid + (spread * weight)
            logger.debug(f"Bot {self.bot_id} - Generated trade price: ${trade_price:.2f} (weighted: {weight:.2f})")
            self._log("INFO", f"Generated trade price: ${trade_price:.2f} (weighted: {weight:.2f})")
            
            # Step 7: Place BOTH buy and sell orders
            logger.debug(f"Bot {self.bot_id} - Step 7: Placing orders")
            # Calculate buy and sell prices
            sell_price = trade_price + (spread * 0.1)  # Slightly above trade price
            buy_price = trade_price - (spread * 0.1)   # Slightly below trade price
            
            logger.debug(f"Bot {self.bot_id} - Sell price: ${sell_price:.2f}, Buy price: ${buy_price:.2f}")
            
            volume = float(bot.trade_volume)
            logger.debug(f"Bot {self.bot_id} - Trade volume: {volume}")
            
            # Flag to track if any orders were placed
            orders_placed = False
            
            # First try to place a sell order
            logger.debug(f"Bot {self.bot_id} - Attempting to place SELL order")
            try:
                # Check if we have enough base currency for sell order
                sell_possible = base_balance >= volume
                if not sell_possible:
                    logger.debug(f"Bot {self.bot_id} - Insufficient {base_currency} balance: {base_balance:.8f} < {volume:.8f}")
                    self._log("WARNING", f"Insufficient {base_currency} balance for SELL order: {base_balance:.8f} < {volume:.8f}")
                else:
                    # Place sell order
                    sell_order_id = f"mock-sell-{int(time.time())}-{random.randint(1000, 9999)}"
                    logger.debug(f"Bot {self.bot_id} - Placing SELL order: {volume:.8f} {base_currency} @ ${sell_price:.2f} (ID: {sell_order_id})")
                    self._log("INFO", f"Placing SELL order: {volume:.8f} {base_currency} @ ${sell_price:.2f}")
                    self._save_order("SELL", sell_order_id, sell_price, volume)
                    orders_placed = True
                    logger.debug(f"Bot {self.bot_id} - SELL order placed successfully")
            except Exception as e:
                logger.error(f"Error placing SELL order: {str(e)}")
                logger.error(traceback.format_exc())
                self._log("ERROR", f"Error placing SELL order: {str(e)}")
            
            # Now try to place a buy order (separate from sell order)
            logger.debug(f"Bot {self.bot_id} - Attempting to place BUY order")
            try:
                # Check if we have enough quote currency for buy order
                buy_cost = volume * buy_price
                buy_possible = quote_balance >= buy_cost
                if not buy_possible:
                    logger.debug(f"Bot {self.bot_id} - Insufficient {quote_currency} balance: {quote_balance:.2f} < {buy_cost:.2f}")
                    self._log("WARNING", f"Insufficient {quote_currency} balance for BUY order: {quote_balance:.2f} < {buy_cost:.2f}")
                else:
                    # Place buy order
                    buy_order_id = f"mock-buy-{int(time.time())}-{random.randint(1000, 9999)}"
                    logger.debug(f"Bot {self.bot_id} - Placing BUY order: {volume:.8f} {base_currency} @ ${buy_price:.2f} (ID: {buy_order_id})")
                    self._log("INFO", f"Placing BUY order: {volume:.8f} {base_currency} @ ${buy_price:.2f}")
                    self._save_order("BUY", buy_order_id, buy_price, volume)
                    orders_placed = True
                    logger.debug(f"Bot {self.bot_id} - BUY order placed successfully")
            except Exception as e:
                logger.error(f"Error placing BUY order: {str(e)}")
                logger.error(traceback.format_exc())
                self._log("ERROR", f"Error placing BUY order: {str(e)}")
            
            # Check if we've completed the total trade volume from the bot configuration
            from .models import Order
            total_volume_executed = Order.objects.filter(bot_config_id=self.bot_id).aggregate(
                total=models.Sum('volume')
            )['total'] or 0
            
            if total_volume_executed >= float(bot.trade_volume):
                logger.debug(f"Bot {self.bot_id} - Total trade volume completed. Stopping bot.")
                self._log("INFO", f"Total trade volume of {bot.trade_volume} completed. Auto-stopping bot.")
                self.stop_event.set()
                return
            
            # Log summary of trading cycle
            if orders_placed:
                logger.debug(f"Bot {self.bot_id} - Trading cycle completed successfully with orders placed")
                self._log("INFO", f"Trading cycle completed - created volume with order(s)")
            else:
                logger.debug(f"Bot {self.bot_id} - No orders placed in this cycle")
                self._log("WARNING", "No orders placed in this cycle due to insufficient balance or errors")
                
        except Exception as e:
            logger.error(f"Error in trading cycle: {str(e)}")
            logger.error(traceback.format_exc())
            self._log("ERROR", f"Error in trading cycle: {str(e)}")
    
    def _log(self, level, message):
        """Write a log message to the database with debug logging"""
        logger.debug(f"Bot {self.bot_id} - Logging to database: [{level}] {message}")
        try:
            from .models import BotLog
            with transaction.atomic():
                BotLog.objects.create(
                    bot_config_id=self.bot_id,
                    level=level,
                    message=message
                )
            logger.debug(f"Bot {self.bot_id} - Log saved to database")
        except Exception as e:
            logger.error(f"Error logging message to database: {str(e)}")
            logger.error(traceback.format_exc())
    
    def _save_order(self, order_type, order_id, price, volume):
        """Save an order to the database with debug logging"""
        logger.debug(f"Bot {self.bot_id} - Saving {order_type} order to database: {volume} @ ${price:.2f}")
        try:
            from .models import Order, BotConfig
            with transaction.atomic():
                bot_config = BotConfig.objects.get(id=self.bot_id)
                Order.objects.create(
                    bot_config_id=self.bot_id,
                    order_id=order_id,
                    pair=bot_config.pair,
                    order_type=order_type,
                    price=price,
                    volume=volume,
                    status='OPEN'
                )
            logger.debug(f"Bot {self.bot_id} - Order saved to database")
        except Exception as e:
            logger.error(f"Error saving order to database: {str(e)}")
            logger.error(traceback.format_exc())
    
    def _mark_stopped(self):
        """Mark the bot as stopped in the database with debug logging"""
        logger.debug(f"Bot {self.bot_id} - Marking as stopped in database")
        try:
            from .models import BotConfig
            with transaction.atomic():
                BotConfig.objects.filter(id=self.bot_id).update(is_active=False)
            logger.debug(f"Bot {self.bot_id} - Marked as stopped in database")
        except Exception as e:
            logger.error(f"Error marking bot as stopped in database: {str(e)}")
            logger.error(traceback.format_exc())


class MockBotManager:
    """
    Manager class to handle multiple mock trading bots with diagnostic logging.
    """
    def __init__(self):
        """Initialize the bot manager"""
        logger.debug("Initializing Mock Bot Manager (Diagnostic Version)")
        self.bots = {}
    
    def start_bot(self, bot_id):
        """Start a trading bot"""
        logger.debug(f"Request to start bot {bot_id}")
        if bot_id in self.bots:
            logger.warning(f"Bot {bot_id} is already running")
            return False
        
        try:
            # Create a new bot instance
            logger.debug(f"Creating new bot instance for {bot_id}")
            bot = MockTradingBot(bot_id)
            
            # Start the bot
            logger.debug(f"Starting bot {bot_id}")
            success = bot.start()
            
            if success:
                self.bots[bot_id] = bot
                logger.info(f"Bot {bot_id} started successfully")
                return True
            else:
                logger.error(f"Failed to start bot {bot_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error starting bot {bot_id}: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def stop_bot(self, bot_id):
        """Stop a trading bot"""
        logger.debug(f"Request to stop bot {bot_id}")
        if bot_id not in self.bots:
            logger.warning(f"Bot {bot_id} is not running")
            return False
        
        try:
            bot = self.bots[bot_id]
            
            # Stop the bot
            logger.debug(f"Stopping bot {bot_id}")
            success = bot.stop()
            
            if success:
                del self.bots[bot_id]
                logger.info(f"Bot {bot_id} stopped successfully")
                return True
            else:
                logger.error(f"Failed to stop bot {bot_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error stopping bot {bot_id}: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def stop_all_bots(self):
        """Stop all running bots"""
        logger.debug("Stopping all bots")
        for bot_id in list(self.bots.keys()):
            self.stop_bot(bot_id)
    
    def shutdown(self):
        """Shutdown the bot manager"""
        logger.debug("Shutting down Mock Bot Manager")
        self.stop_all_bots()
        logger.info("Bot manager shutdown complete")

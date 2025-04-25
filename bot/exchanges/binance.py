import logging
import aiohttp
from binance import AsyncClient
from binance.exceptions import BinanceAPIException
from .base import BaseExchangeClient

logger = logging.getLogger('bot')

class BinanceClient(BaseExchangeClient):
    """
    Client for the Binance exchange API using python-binance.
    """
    
    def __init__(self, api_key, secret_key):
        super().__init__(api_key, secret_key)
        self.client = None
    
    async def _init_client(self):
        """Initialize the Binance client if not already done"""
        if self.client is None:
            self.client = await AsyncClient.create(self.api_key, self.secret_key)
    
    async def _close_client(self):
        """Close the Binance client if it exists"""
        if self.client:
            await self.client.close_connection()
            self.client = None
    
    async def get_wallet_balance(self):
        """
        Get wallet balance from Binance.
        
        Returns:
            dict: User balances
        """
        await self._init_client()
        
        try:
            account = await self.client.get_account()
            
            # Format the response into a consistent format
            balances = {}
            for asset in account['balances']:
                free = float(asset['free'])
                locked = float(asset['locked'])
                if free > 0 or locked > 0:
                    balances[asset['asset']] = {
                        'free': free,
                        'locked': locked,
                        'total': free + locked
                    }
            
            return balances
            
        except BinanceAPIException as e:
            logger.error(f"Binance API error: {str(e)}")
            raise
    
    async def get_order_book(self, pair):
        """
        Get order book for a trading pair.
        
        Args:
            pair (str): Trading pair symbol (e.g., "BTCUSDT")
            
        Returns:
            dict: Order book with bids and asks
        """
        await self._init_client()
        
        try:
            # Convert pair format if needed (e.g., BTC_USDT to BTCUSDT)
            pair = pair.replace('_', '')
            
            depth = await self.client.get_order_book(symbol=pair, limit=20)
            
            # Format response to a standard format
            return {
                'bids': [[float(price), float(qty)] for price, qty in depth['bids']],
                'asks': [[float(price), float(qty)] for price, qty in depth['asks']]
            }
            
        except BinanceAPIException as e:
            logger.error(f"Binance API error: {str(e)}")
            raise
    
    async def get_24h_ticker(self, pair):
        """
        Get 24-hour ticker data for a trading pair.
        
        Args:
            pair (str): Trading pair symbol (e.g., "BTCUSDT")
            
        Returns:
            dict: 24-hour ticker data
        """
        await self._init_client()
        
        try:
            # Convert pair format if needed
            pair = pair.replace('_', '')
            
            ticker = await self.client.get_ticker(symbol=pair)
            
            # Format response to a standard format
            return {
                'symbol': ticker['symbol'],
                'last_price': float(ticker['lastPrice']),
                'high_price': float(ticker['highPrice']),
                'low_price': float(ticker['lowPrice']),
                'volume': float(ticker['volume']),
                'quote_volume': float(ticker['quoteVolume']),
                'price_change': float(ticker['priceChange']),
                'price_change_percent': float(ticker['priceChangePercent'])
            }
            
        except BinanceAPIException as e:
            logger.error(f"Binance API error: {str(e)}")
            raise
    
    async def place_order(self, order_type, pair, volume, price):
        """
        Place an order on Binance.
        
        Args:
            order_type (str): 'buy' or 'sell'
            pair (str): Trading pair symbol (e.g., "BTCUSDT")
            volume (float): Amount to buy/sell
            price (float): Price for the order
            
        Returns:
            dict: Order details
        """
        await self._init_client()
        
        try:
            # Convert pair format if needed
            pair = pair.replace('_', '')
            
            if order_type.lower() == 'buy':
                order = await self.client.create_order(
                    symbol=pair,
                    side='BUY',
                    type='LIMIT',
                    timeInForce='GTC',
                    quantity=volume,
                    price=price
                )
            else:
                order = await self.client.create_order(
                    symbol=pair,
                    side='SELL',
                    type='LIMIT',
                    timeInForce='GTC',
                    quantity=volume,
                    price=price
                )
            
            return {
                'order_id': order['orderId'],
                'symbol': order['symbol'],
                'status': order['status'],
                'type': order['type'],
                'side': order['side'],
                'price': float(order['price']),
                'orig_qty': float(order['origQty']),
                'executed_qty': float(order['executedQty']),
                'time': order['transactTime']
            }
            
        except BinanceAPIException as e:
            logger.error(f"Binance API error: {str(e)}")
            raise
    
    async def get_pairs(self):
        """
        Get all trading pairs from Binance.
        
        Returns:
            list: List of trading pair information
        """
        await self._init_client()
        
        try:
            exchange_info = await self.client.get_exchange_info()
            
            pairs = []
            for symbol in exchange_info['symbols']:
                # Skip pairs that are not trading
                if symbol['status'] != 'TRADING':
                    continue
                
                # Find the filters for min/max quantity
                min_qty = None
                max_qty = None
                price_precision = None
                qty_precision = None
                
                for f in symbol['filters']:
                    if f['filterType'] == 'LOT_SIZE':
                        min_qty = float(f['minQty'])
                        max_qty = float(f['maxQty'])
                    elif f['filterType'] == 'PRICE_FILTER':
                        temp = f['tickSize'].rstrip('0').rstrip('.')
                        price_precision = len(f['tickSize']) - 1 - (len(temp) if '.' in f['tickSize'] else 0)
                
                qty_precision = symbol.get('baseAssetPrecision', 8)
                
                pairs.append({
                    'symbol': symbol['symbol'],
                    'base_asset': symbol['baseAsset'],
                    'quote_asset': symbol['quoteAsset'],
                    'min_quantity': min_qty,
                    'max_quantity': max_qty,
                    'price_precision': price_precision if price_precision is not None else 8,
                    'quantity_precision': qty_precision
                })
            
            return pairs
            
        except BinanceAPIException as e:
            logger.error(f"Binance API error: {str(e)}")
            raise

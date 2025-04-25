import aiohttp
import hashlib
import hmac
import json
import logging
import time
from urllib.parse import urlencode

from .base import BaseExchangeClient

logger = logging.getLogger('bot')

class PionexClient(BaseExchangeClient):
    """
    Client for the Pionex exchange API.
    """
    BASE_URL = "https://api.pionex.com"
    
    def __init__(self, api_key, secret_key):
        super().__init__(api_key, secret_key)
        self.session = None
    
    async def _init_session(self):
        """Initialize aiohttp session if not already done"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
    
    async def _close_session(self):
        """Close aiohttp session if it exists"""
        if self.session:
            await self.session.close()
            self.session = None
    
    def _generate_signature(self, params):
        """
        Generate HMAC-SHA256 signature for API request.
        
        Args:
            params (dict): Request parameters
            
        Returns:
            str: Hex-encoded signature
        """
        query_string = urlencode(params)
        signature = hmac.new(
            self.secret_key.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    async def _make_request(self, method, endpoint, params=None, auth=True):
        """
        Make a request to the Pionex API.
        
        Args:
            method (str): HTTP method ('GET', 'POST', etc.)
            endpoint (str): API endpoint
            params (dict, optional): Request parameters
            auth (bool): Whether to use authentication
            
        Returns:
            dict: Response data
        """
        await self._init_session()
        
        url = f"{self.BASE_URL}{endpoint}"
        
        if params is None:
            params = {}
        
        headers = {'Content-Type': 'application/json'}
        
        if auth:
            # Add timestamp for auth
            timestamp = int(time.time() * 1000)
            params['timestamp'] = timestamp
            
            # Generate signature
            signature = self._generate_signature(params)
            
            # Set auth headers properly
            headers.update({
                'X-API-KEY': self.api_key,
                'X-TIMESTAMP': str(timestamp),
                'X-SIGNATURE': signature
            })
        
        try:
            if method == 'GET':
                # For GET requests, add params to URL query string
                query_string = urlencode(params)
                full_url = f"{url}?{query_string}" if query_string else url
                
                logger.debug(f"Making GET request to {full_url}")
                async with self.session.get(full_url, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"API error: Status {response.status}, Response: {error_text}")
                        raise Exception(f"API error: Status {response.status}, Response: {error_text}")
                    
                    # Get the content type
                    content_type = response.headers.get('Content-Type', '')
                    
                    # Get the raw text response
                    raw_response = await response.text()
                    logger.debug(f"Raw response: {raw_response}")
                    
                    # Try to parse as JSON regardless of content type
                    try:
                        data = json.loads(raw_response)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse response as JSON: {str(e)}")
                        logger.error(f"Raw response: {raw_response}")
                        raise Exception(f"Failed to parse response as JSON: {str(e)}")
            else:  # POST
                logger.debug(f"Making POST request to {url}")
                async with self.session.post(url, headers=headers, json=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"API error: Status {response.status}, Response: {error_text}")
                        raise Exception(f"API error: Status {response.status}, Response: {error_text}")
                    
                    # Get the raw text response
                    raw_response = await response.text()
                    logger.debug(f"Raw response: {raw_response}")
                    
                    # Try to parse as JSON
                    try:
                        data = json.loads(raw_response)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse response as JSON: {str(e)}")
                        logger.error(f"Raw response: {raw_response}")
                        raise Exception(f"Failed to parse response as JSON: {str(e)}")
            
            if data.get('code') and data['code'] != 0:
                logger.error(f"Pionex API error: {data}")
                raise Exception(f"Pionex API error: {data.get('msg', 'Unknown error')}")
                
            return data.get('data', data)
        
        except aiohttp.ClientError as e:
            logger.error(f"Request error: {str(e)}")
            raise Exception(f"Network error: {str(e)}")
    
    async def get_wallet_balance(self):
        """
        Get wallet balance from Pionex.
        
        Returns:
            dict: User balances
        """
        endpoint = "/api/v1/account/balances"
        try:
            response = await self._make_request('GET', endpoint)
            logger.debug(f"Wallet balance response: {response}")
            
            # Format the response into a consistent format
            balances = {}
            
            # Check if response is a list (expected format)
            if isinstance(response, list):
                for asset in response:
                    balances[asset['asset']] = {
                        'free': float(asset['free']),
                        'locked': float(asset['locked']),
                        'total': float(asset['free']) + float(asset['locked'])
                    }
            else:
                # If not a list, log the unexpected format but return what we have
                logger.warning(f"Unexpected wallet balance format: {response}")
                return response
            
            return balances
        except Exception as e:
            logger.error(f"Error in get_wallet_balance: {str(e)}")
            raise
    
    async def get_order_book(self, pair):
        """
        Get order book for a trading pair.
        
        Args:
            pair (str): Trading pair symbol (e.g., "BTC_USDT")
            
        Returns:
            dict: Order book with bids and asks
        """
        endpoint = "/api/v1/market/depth"
        params = {
            'symbol': pair,
            'limit': 20  # Request 20 levels
        }
        
        response = await self._make_request('GET', endpoint, params, auth=False)
        
        # Format response to a standard format
        return {
            'bids': [[float(price), float(qty)] for price, qty in response['bids']],
            'asks': [[float(price), float(qty)] for price, qty in response['asks']]
        }
    
    async def get_24h_ticker(self, pair):
        """
        Get 24-hour ticker data for a trading pair.
        
        Args:
            pair (str): Trading pair symbol (e.g., "BTC_USDT")
            
        Returns:
            dict: 24-hour ticker data
        """
        endpoint = "/api/v1/market/ticker"
        params = {'symbol': pair}
        
        response = await self._make_request('GET', endpoint, params, auth=False)
        
        # Format response to a standard format
        return {
            'symbol': response['symbol'],
            'last_price': float(response['lastPrice']),
            'high_price': float(response['highPrice']),
            'low_price': float(response['lowPrice']),
            'volume': float(response['volume']),
            'quote_volume': float(response['quoteVolume']),
            'price_change': float(response['priceChange']),
            'price_change_percent': float(response['priceChangePercent'])
        }
    
    async def place_order(self, order_type, pair, volume, price):
        """
        Place an order on Pionex.
        
        Args:
            order_type (str): 'buy' or 'sell'
            pair (str): Trading pair symbol (e.g., "BTC_USDT")
            volume (float): Amount to buy/sell
            price (float): Price for the order
            
        Returns:
            dict: Order details
        """
        endpoint = "/api/v1/order"
        params = {
            'symbol': pair,
            'side': order_type.upper(),
            'type': 'LIMIT',
            'timeInForce': 'GTC',
            'quantity': str(volume),
            'price': str(price)
        }
        
        response = await self._make_request('POST', endpoint, params)
        
        return {
            'order_id': response['orderId'],
            'symbol': response['symbol'],
            'status': response['status'],
            'type': response['type'],
            'side': response['side'],
            'price': float(response['price']),
            'orig_qty': float(response['origQty']),
            'executed_qty': float(response['executedQty']),
            'time': response['time']
        }
    
    async def get_pairs(self):
        """
        Get all trading pairs from Pionex.
        
        Returns:
            list: List of trading pair information
        """
        endpoint = "/api/v1/market/symbols"
        response = await self._make_request('GET', endpoint, auth=False)
        
        pairs = []
        for symbol in response:
            pairs.append({
                'symbol': symbol['symbol'],
                'base_asset': symbol['baseAsset'],
                'quote_asset': symbol['quoteAsset'],
                'min_quantity': float(symbol['minQty']),
                'max_quantity': float(symbol['maxQty']) if 'maxQty' in symbol else None,
                'price_precision': symbol['pricePrecision'],
                'quantity_precision': symbol['quantityPrecision']
            })
        
        return pairs

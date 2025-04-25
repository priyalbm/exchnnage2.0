import time
import hmac
import hashlib
import base64
import json
import logging
import requests
from urllib.parse import urlencode
from .base import ExchangeClient

logger = logging.getLogger(__name__)

class PionexClient(ExchangeClient):
    """
    Client for Pionex exchange API
    """
    def __init__(self, api_key=None, api_secret=None, base_url=None):
        super().__init__(api_key, api_secret)
        self.base_url = base_url or "https://api.pionex.com"
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        
        # Add a file handler for debugging
        file_handler = logging.FileHandler('pionex_client.log')
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(file_handler)

    def _generate_signature(self, timestamp, method, request_path, body=None):
        """Generate signature for Pionex API"""
        try:
            # Step 1: Create the string to sign
            if body and isinstance(body, dict):
                body_str = json.dumps(body)
            else:
                body_str = body or ""
                
            string_to_sign = f"{timestamp}{method}{request_path}{body_str}"
            
            # Step 2: Create the signature
            signature = hmac.new(
                self.api_secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            return signature
        except Exception as e:
            self.logger.error(f"Error generating signature: {str(e)}", exc_info=True)
            return None

    def _make_request(self, method, endpoint, params=None, data=None):
        """Make request to Pionex API with proper error handling"""
        try:
            # Construct full URL
            url = f"{self.base_url}{endpoint}"
            
            # Add query parameters if provided
            if params:
                query_string = urlencode(params)
                url = f"{url}?{query_string}"
                
            # Generate timestamp and signature
            timestamp = str(int(time.time() * 1000))
            signature = self._generate_signature(timestamp, method, endpoint, data)
            
            if not signature:
                return {"error": True, "detail": "Failed to generate signature"}
                
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'X-API-KEY': self.api_key,
                'X-TIMESTAMP': timestamp,
                'X-SIGNATURE': signature
            }
            
            # Log request details (for debugging)
            self.logger.debug(f"Making {method} request to {url}")
            self.logger.debug(f"Headers: {headers}")
            if data:
                self.logger.debug(f"Data: {data}")
                
            # Make the request
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=30)
            else:
                return {"error": True, "detail": f"Unsupported method: {method}"}
                
            # Log response
            self.logger.debug(f"Response status: {response.status_code}")
            self.logger.debug(f"Response body: {response.text}")
            
            # Check for HTTP errors
            if response.status_code != 200:
                return {
                    "error": True,
                    "detail": f"HTTP error {response.status_code}: {response.text}"
                }
                
            # Parse JSON response
            result = response.json()
            
            # Check for API errors
            if result.get('code') != 0:
                return {
                    "error": True,
                    "detail": f"API error {result.get('code')}: {result.get('message')}"
                }
                
            # Return successful response
            return {
                "error": False,
                "data": result.get('data', {})
            }
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error: {str(e)}", exc_info=True)
            return {"error": True, "detail": f"Request error: {str(e)}"}
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error: {str(e)}", exc_info=True)
            return {"error": True, "detail": f"Invalid JSON response: {str(e)}"}
        except Exception as e:
            self.logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return {"error": True, "detail": f"Unexpected error: {str(e)}"}

    def get_trading_pairs(self):
        """Get all trading pairs"""
        try:
            self.logger.info("Getting trading pairs")
            response = self._make_request('GET', '/api/v1/market/symbols')
            
            if response.get('error'):
                return response
                
            # Format the response
            pairs = []
            for pair in response.get('data', []):
                pairs.append({
                    'symbol': pair.get('symbol'),
                    'baseCurrency': pair.get('baseCurrency'),
                    'quoteCurrency': pair.get('quoteCurrency'),
                    'basePrecision': pair.get('basePrecision', 8),
                    'quotePrecision': pair.get('quotePrecision', 8),
                    'minTradeAmount': pair.get('minTradeAmount', 0)
                })
                
            return {"error": False, "data": pairs}
        except Exception as e:
            self.logger.error(f"Error getting trading pairs: {str(e)}", exc_info=True)
            return {"error": True, "detail": f"Error getting trading pairs: {str(e)}"}

    def get_ticker(self, symbol):
        """Get ticker for a symbol"""
        try:
            self.logger.info(f"Getting ticker for {symbol}")
            response = self._make_request('GET', '/api/v1/market/ticker', {'symbol': symbol})
            
            if response.get('error'):
                return response
                
            # Format the response
            ticker_data = response.get('data', {})
            return {
                "error": False,
                "data": {
                    "symbol": symbol,
                    "lastPrice": float(ticker_data.get('last', 0)),
                    "bidPrice": float(ticker_data.get('buy', 0)),
                    "askPrice": float(ticker_data.get('sell', 0)),
                    "volume": float(ticker_data.get('vol', 0)),
                    "timestamp": int(ticker_data.get('time', time.time() * 1000))
                }
            }
        except Exception as e:
            self.logger.error(f"Error getting ticker: {str(e)}", exc_info=True)
            return {"error": True, "detail": f"Error getting ticker: {str(e)}"}

    def get_order_book(self, symbol):
        """Get order book for a symbol"""
        try:
            self.logger.info(f"Getting order book for {symbol}")
            response = self._make_request('GET', '/api/v1/market/depth', {'symbol': symbol, 'limit': 20})
            
            if response.get('error'):
                return response
                
            # Format the response
            order_book = response.get('data', {})
            return {
                "error": False,
                "data": {
                    "symbol": symbol,
                    "bids": order_book.get('bids', []),
                    "asks": order_book.get('asks', []),
                    "timestamp": int(time.time() * 1000)
                }
            }
        except Exception as e:
            self.logger.error(f"Error getting order book: {str(e)}", exc_info=True)
            return {"error": True, "detail": f"Error getting order book: {str(e)}"}

    def get_balance(self):
        """Get account balance"""
        try:
            self.logger.info("Getting account balance")
            response = self._make_request('GET', '/api/v1/account/balances')
            
            if response.get('error'):
                return response
                
            # Format the response
            balances = {}
            for asset in response.get('data', []):
                currency = asset.get('currency', '')
                balances[currency] = {
                    "available": float(asset.get('available', 0)),
                    "locked": float(asset.get('locked', 0))
                }
                
            return {"error": False, "data": balances}
        except Exception as e:
            self.logger.error(f"Error getting balance: {str(e)}", exc_info=True)
            return {"error": True, "detail": f"Error getting balance: {str(e)}"}

    def create_order(self, symbol, side, order_type, quantity, price=None):
        """Create a new order"""
        try:
            self.logger.info(f"Creating {side} {order_type} order: {quantity} {symbol} @ {price}")
            
            # Prepare order data
            order_data = {
                "symbol": symbol,
                "side": side.upper(),
                "type": order_type.upper(),
                "quantity": str(quantity)
            }
            
            # Add price for limit orders
            if order_type.upper() == 'LIMIT' and price is not None:
                order_data["price"] = str(price)
                
            response = self._make_request('POST', '/api/v1/trade/order', data=order_data)
            
            if response.get('error'):
                return response
                
            # Format the response
            order = response.get('data', {})
            return {
                "error": False,
                "data": {
                    "orderId": order.get('orderId', ''),
                    "symbol": symbol,
                    "side": side,
                    "type": order_type,
                    "price": price,
                    "quantity": quantity,
                    "status": "PENDING",
                    "timestamp": int(time.time() * 1000)
                }
            }
        except Exception as e:
            self.logger.error(f"Error creating order: {str(e)}", exc_info=True)
            return {"error": True, "detail": f"Error creating order: {str(e)}"}

    def cancel_order(self, symbol, order_id):
        """Cancel an order"""
        try:
            self.logger.info(f"Cancelling order {order_id} for {symbol}")
            
            order_data = {
                "symbol": symbol,
                "orderId": order_id
            }
            
            response = self._make_request('POST', '/api/v1/trade/cancel', data=order_data)
            
            if response.get('error'):
                return response
                
            return {
                "error": False,
                "data": {
                    "orderId": order_id,
                    "symbol": symbol
                }
            }
        except Exception as e:
            self.logger.error(f"Error cancelling order: {str(e)}", exc_info=True)
            return {"error": True, "detail": f"Error cancelling order: {str(e)}"}

    def check_order_status(self, symbol, order_id):
        """Check order status"""
        try:
            self.logger.info(f"Checking status of order {order_id} for {symbol}")
            
            params = {
                "symbol": symbol,
                "orderId": order_id
            }
            
            response = self._make_request('GET', '/api/v1/trade/order', params=params)
            
            if response.get('error'):
                return response
                
            # Format the response
            order = response.get('data', {})
            return {
                "error": False,
                "data": {
                    "orderId": order.get('orderId', ''),
                    "symbol": symbol,
                    "status": order.get('status', ''),
                    "price": float(order.get('price', 0)),
                    "quantity": float(order.get('quantity', 0)),
                    "side": order.get('side', ''),
                    "type": order.get('type', ''),
                    "timestamp": int(order.get('time', time.time() * 1000))
                }
            }
        except Exception as e:
            self.logger.error(f"Error checking order status: {str(e)}", exc_info=True)
            return {"error": True, "detail": f"Error checking order status: {str(e)}"}
    
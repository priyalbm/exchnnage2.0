import time
import hmac
import hashlib
import urllib.parse
import requests
import logging
from .base import ExchangeClient

# Set up logging
logger = logging.getLogger(__name__)

class BinanceClient(ExchangeClient):
    """
    Binance exchange client implementation
    """
    
    def __init__(self, api_key=None, api_secret=None, base_url=None):
        super().__init__(api_key, api_secret, base_url or "https://api.binance.com")
    
    def _sign_request(self, params=None):
        # Implementation of Binance signing mechanism
        if params is None:
            params = {}
        
        params['timestamp'] = str(int(time.time() * 1000))
        query_string = urllib.parse.urlencode(params)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        params['signature'] = signature
        return params
    
    def _request(self, method, endpoint, params=None, signed=False):
        if params is None:
            params = {}
        
        headers = {}
        if self.api_key:
            headers['X-MBX-APIKEY'] = self.api_key
        
        if signed and self.api_secret:
            params = self._sign_request(params)
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, params=params, headers=headers)
            elif method == 'POST':
                response = requests.post(url, params=params, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, params=params, headers=headers)
            else:
                return {'error': True, 'detail': 'Invalid HTTP method'}
            
            response.raise_for_status()
            return {'error': False, 'data': response.json()}
        except requests.exceptions.RequestException as e:
            logger.error(f"Binance API Error: {e}")
            if hasattr(e, 'response') and e.response:
                try:
                    error_data = e.response.json()
                    return {'error': True, 'detail': error_data.get('msg', str(e))}
                except:
                    return {'error': True, 'detail': e.response.text}
            return {'error': True, 'detail': str(e)}
    
    def get_trading_pairs(self):
        """Get available trading pairs from Binance"""
        response = self._request('GET', '/api/v3/exchangeInfo')
        if response.get('error', False):
            return response
        
        result = []
        for symbol_data in response.get('data', {}).get('symbols', []):
            if symbol_data.get('status') == 'TRADING':
                # Find precision from filters
                price_filter = next((f for f in symbol_data.get('filters', []) if f.get('filterType') == 'PRICE_FILTER'), {})
                lot_filter = next((f for f in symbol_data.get('filters', []) if f.get('filterType') == 'LOT_SIZE'), {})
                
                result.append({
                    'symbol': symbol_data.get('symbol'),
                    'baseCurrency': symbol_data.get('baseAsset'),
                    'quoteCurrency': symbol_data.get('quoteAsset'),
                    'basePrecision': symbol_data.get('baseAssetPrecision', 8),
                    'quotePrecision': symbol_data.get('quoteAssetPrecision', 8),
                    'minAmount': price_filter.get('minPrice', '0.00000001'),
                    'minTradeSize': lot_filter.get('minQty', '0.00000001')
                })
        
        return {'error': False, 'data': result}
    
    def get_ticker(self, symbol):
        """Get ticker data from Binance"""
        response = self._request('GET', '/api/v3/ticker/24hr', {'symbol': symbol})
        if response.get('error', False):
            return response
        
        ticker = response.get('data', {})
        return {
            'error': False,
            'data': {
                'symbol': symbol,
                'lastPrice': float(ticker.get('lastPrice', 0)),
                'bidPrice': float(ticker.get('bidPrice', 0)),
                'askPrice': float(ticker.get('askPrice', 0)),
                'volume': float(ticker.get('volume', 0)),
                'high': float(ticker.get('highPrice', 0)),
                'low': float(ticker.get('lowPrice', 0))
            }
        }
    
    def get_order_book(self, symbol):
        """Get order book from Binance"""
        response = self._request('GET', '/api/v3/depth', {'symbol': symbol, 'limit': 20})
        if response.get('error', False):
            return response
        
        order_book = response.get('data', {})
        # Transform to match our standard format
        bids = [[price, quantity] for price, quantity in order_book.get('bids', [])]
        asks = [[price, quantity] for price, quantity in order_book.get('asks', [])]
        
        return {
            'error': False,
            'data': {
                'bids': bids,
                'asks': asks
            }
        }
    
    def get_balance(self):
        """Get account balance from Binance"""
        response = self._request('GET', '/api/v3/account', {}, signed=True)
        if response.get('error', False):
            return response
        
        balances = []
        for bal in response.get('data', {}).get('balances', []):
            free = float(bal.get('free', 0))
            locked = float(bal.get('locked', 0))
            total = free + locked
            
            if total > 0:  # Only include non-zero balances
                balances.append({
                    'asset': bal.get('asset', ''),
                    'free': free,
                    'locked': locked,
                    'total': total
                })
        
        return {'error': False, 'data': balances}
    
    def create_order(self, symbol, side, order_type, quantity, price=None):
        """Create a new order on Binance"""
        params = {
            'symbol': symbol,
            'side': side.upper(),
            'type': order_type.upper(),
            'quantity': quantity
        }
        
        if order_type.upper() == 'LIMIT':
            if price is None:
                return {'error': True, 'detail': 'Price is required for limit orders'}
            params['price'] = price
            params['timeInForce'] = 'GTC'  # Good Till Canceled
        
        response = self._request('POST', '/api/v3/order', params, signed=True)
        if response.get('error', False):
            return response
        
        order_data = response.get('data', {})
        return {
            'error': False,
            'data': {
                'orderId': order_data.get('orderId'),
                'symbol': symbol,
                'status': order_data.get('status', 'NEW')
            }
        }
    
    def cancel_order(self, symbol, order_id):
        """Cancel an existing order on Binance"""
        params = {
            'symbol': symbol,
            'orderId': order_id
        }
        
        response = self._request('DELETE', '/api/v3/order', params, signed=True)
        if response.get('error', False):
            return response
        
        return {
            'error': False,
            'data': {'success': True}
        }
    
    def check_order_status(self, symbol, order_id):
        """Check status of an existing order on Binance"""
        params = {
            'symbol': symbol,
            'orderId': order_id
        }
        
        response = self._request('GET', '/api/v3/order', params, signed=True)
        if response.get('error', False):
            return response
        
        order = response.get('data', {})
        return {
            'error': False,
            'data': {
                'orderId': order.get('orderId'),
                'symbol': symbol,
                'side': order.get('side'),
                'type': order.get('type'),
                'price': float(order.get('price', 0)),
                'quantity': float(order.get('origQty', 0)),
                'executed': float(order.get('executedQty', 0)),
                'status': order.get('status')
            }
        }
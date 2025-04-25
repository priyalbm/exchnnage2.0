import time
import hmac
import hashlib
import base64
import requests
import json
import uuid
import logging
from .base import ExchangeClient

# Set up logging
logger = logging.getLogger(__name__)

class KuCoinClient(ExchangeClient):
    """
    KuCoin exchange client implementation
    """
    
    def __init__(self, api_key=None, api_secret=None, base_url=None, passphrase=None):
        super().__init__(api_key, api_secret, base_url or "https://api.kucoin.com")
        self.passphrase = passphrase or ""  # API passphrase is required for KuCoin
    
    def _get_kucoin_signature(self, endpoint, method, data=None, params=None):
        # Generate KuCoin API signature according to their documentation
        now = int(time.time() * 1000)
        str_to_sign = f"{now}{method}{endpoint}"
        
        # Add parameters to signature if they exist
        if params:
            query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
            str_to_sign += f"?{query_string}"
        
        # Add body to signature if it exists
        if data:
            str_to_sign += json.dumps(data)
        
        # Generate signature
        signature = base64.b64encode(
            hmac.new(
                self.api_secret.encode('utf-8'),
                str_to_sign.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        # Encrypt passphrase
        passphrase = base64.b64encode(
            hmac.new(
                self.api_secret.encode('utf-8'),
                self.passphrase.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        return {
            'KC-API-SIGN': signature,
            'KC-API-TIMESTAMP': str(now),
            'KC-API-KEY': self.api_key,
            'KC-API-PASSPHRASE': passphrase,
            'KC-API-KEY-VERSION': '2'  # API key version
        }
    
    def _request(self, method, endpoint, params=None, data=None, signed=False):
        # Prepare headers
        headers = {
            'Content-Type': 'application/json'
        }
        
        # Add signature headers if needed
        if signed and self.api_key and self.api_secret:
            headers.update(self._get_kucoin_signature(endpoint, method, data, params))
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, params=params, headers=headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, params=params, json=data, headers=headers)
            else:
                return {'error': True, 'detail': 'Invalid HTTP method'}
            
            response.raise_for_status()
            result = response.json()
            
            # KuCoin API returns a standard format with 'code', 'data', and 'msg'
            if result.get('code') != '200000':
                return {'error': True, 'detail': result.get('msg', 'Unknown error')}
            
            return {'error': False, 'data': result.get('data')}
        except requests.exceptions.RequestException as e:
            logger.error(f"KuCoin API Error: {e}")
            if hasattr(e, 'response') and e.response:
                try:
                    error_data = e.response.json()
                    return {'error': True, 'detail': error_data.get('msg', str(e))}
                except:
                    return {'error': True, 'detail': e.response.text}
            return {'error': True, 'detail': str(e)}
    
    def get_trading_pairs(self):
        """Get available trading pairs from KuCoin"""
        response = self._request('GET', '/api/v1/symbols')
        if response.get('error', False):
            return response
        
        result = []
        for symbol_data in response.get('data', []):
            if symbol_data.get('enableTrading', False):
                result.append({
                    'symbol': symbol_data.get('symbol'),
                    'baseCurrency': symbol_data.get('baseCurrency'),
                    'quoteCurrency': symbol_data.get('quoteCurrency'),
                    'basePrecision': int(symbol_data.get('baseIncrement', '0.00000001').count('0')),
                    'quotePrecision': int(symbol_data.get('quoteIncrement', '0.00000001').count('0')),
                    'minAmount': symbol_data.get('quoteMinSize', '0.001'),
                    'minTradeSize': symbol_data.get('baseMinSize', '0.00000001')
                })
        
        return {'error': False, 'data': result}
    
    def get_ticker(self, symbol):
        """Get ticker data from KuCoin"""
        ticker_response = self._request('GET', f'/api/v1/market/orderbook/level1', {'symbol': symbol})
        if ticker_response.get('error', False):
            return ticker_response
        
        stats_response = self._request('GET', f'/api/v1/market/stats', {'symbol': symbol})
        if stats_response.get('error', False):
            return stats_response
        
        ticker = ticker_response.get('data', {})
        stats = stats_response.get('data', {})
        
        return {
            'error': False,
            'data': {
                'symbol': symbol,
                'lastPrice': float(ticker.get('price', 0)),
                'bidPrice': float(ticker.get('bestBid', 0)),
                'askPrice': float(ticker.get('bestAsk', 0)),
                'volume': float(stats.get('vol', 0)),
                'high': float(stats.get('high', 0)),
                'low': float(stats.get('low', 0))
            }
        }
    
    def get_order_book(self, symbol):
        """Get order book from KuCoin"""
        response = self._request('GET', '/api/v1/market/orderbook/level2_20', {'symbol': symbol})
        if response.get('error', False):
            return response
        
        order_book = response.get('data', {})
        
        # KuCoin returns arrays of strings, convert to our standard format
        bids = [[float(bid[0]), float(bid[1])] for bid in order_book.get('bids', [])]
        asks = [[float(ask[0]), float(ask[1])] for ask in order_book.get('asks', [])]
        
        return {
            'error': False,
            'data': {
                'bids': bids,
                'asks': asks
            }
        }
    
    def get_balance(self):
        """Get account balance from KuCoin"""
        response = self._request('GET', '/api/v1/accounts', signed=True)
        if response.get('error', False):
            return response
        
        balances = []
        for bal in response.get('data', []):
            free = float(bal.get('available', 0))
            locked = float(bal.get('holds', 0))
            total = free + locked
            
            if total > 0:  # Only include non-zero balances
                balances.append({
                    'asset': bal.get('currency', ''),
                    'free': free,
                    'locked': locked,
                    'total': total
                })
        
        return {'error': False, 'data': balances}
    
    def create_order(self, symbol, side, order_type, quantity, price=None):
        """Create a new order on KuCoin"""
        client_order_id = f"bot_{uuid.uuid4().hex[:16]}"
        
        data = {
            'clientOid': client_order_id,
            'symbol': symbol,
            'side': side.lower(),  # KuCoin uses lowercase for side
            'type': order_type.lower(),  # KuCoin uses lowercase for order type
            'size': str(quantity)
        }
        
        if order_type.upper() == 'LIMIT':
            if price is None:
                return {'error': True, 'detail': 'Price is required for limit orders'}
            data['price'] = str(price)
        
        response = self._request('POST', '/api/v1/orders', data=data, signed=True)
        if response.get('error', False):
            return response
        
        order_data = response.get('data', {})
        return {
            'error': False,
            'data': {
                'orderId': order_data.get('orderId'),
                'clientOrderId': client_order_id,
                'symbol': symbol,
                'status': 'NEW'
            }
        }
    
    def cancel_order(self, symbol, order_id):
        """Cancel an existing order on KuCoin"""
        response = self._request('DELETE', f'/api/v1/orders/{order_id}', signed=True)
        if response.get('error', False):
            return response
        
        return {
            'error': False,
            'data': {'success': True}
        }
    
    def check_order_status(self, symbol, order_id):
        """Check status of an existing order on KuCoin"""
        response = self._request('GET', f'/api/v1/orders/{order_id}', signed=True)
        if response.get('error', False):
            return response
        
        order = response.get('data', {})
        return {
            'error': False,
            'data': {
                'orderId': order.get('id'),
                'symbol': order.get('symbol'),
                'side': order.get('side'),
                'type': order.get('type'),
                'price': float(order.get('price', 0)),
                'quantity': float(order.get('size', 0)),
                'executed': float(order.get('dealSize', 0)),
                'status': order.get('isActive') and 'ACTIVE' or 'DONE'
            }
        }
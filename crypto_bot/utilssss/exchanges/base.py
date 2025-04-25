import abc
import requests
import hmac
import hashlib
import time
from urllib.parse import urlencode

class BaseExchange(metaclass=abc.ABCMeta):
    def __init__(self, api_key=None, api_secret=None):
        self.api_key = api_key
        self.api_secret = api_secret
        
    @property
    @abc.abstractmethod
    def base_url(self):
        pass
    
    def _sign_request(self, data):
        timestamp = str(int(time.time() * 1000))
        data['timestamp'] = timestamp
        query_string = urlencode(sorted(data.items()))
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        data['signature'] = signature
        return data
    
    def _request(self, method, endpoint, params=None, data=None, signed=False):
        url = f"{self.base_url}{endpoint}"
        headers = {}
        
        if signed:
            if not self.api_key or not self.api_secret:
                raise ValueError("API key and secret required for signed requests")
            headers['X-MBX-APIKEY'] = self.api_key
            params = self._sign_request(params or {})
        
        try:
            response = requests.request(method, url, params=params, json=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response:
                error_msg = f"{e.response.status_code} - {e.response.text}"
            return {'error': True, 'message': error_msg}
    
    @abc.abstractmethod
    def get_balance(self):
        pass
    
    @abc.abstractmethod
    def get_symbols(self):
        pass
    
    @abc.abstractmethod
    def get_ticker(self, symbol):
        pass
    
    @abc.abstractmethod
    def get_order_book(self, symbol):
        pass
    
    @abc.abstractmethod
    def create_order(self, symbol, side, order_type, quantity, price=None):
        pass
    
    @abc.abstractmethod
    def cancel_order(self, symbol, order_id):
        pass
    
    @abc.abstractmethod
    def get_order(self, symbol, order_id):
        pass
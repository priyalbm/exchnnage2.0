from .base import BaseExchange

class PionexExchange(BaseExchange):
    @property
    def base_url(self):
        return "https://api.pionex.com"
    
    def get_balance(self):
        endpoint = "/api/v1/account/balances"
        return self._request("GET", endpoint, signed=True)
    
    def get_symbols(self):
        endpoint = "/api/v1/market/symbols"
        response = self._request("GET", endpoint)
        return [symbol['symbol'] for symbol in response.get('data', {}).get('symbols', [])]
    
    def get_ticker(self, symbol):
        endpoint = f"/api/v1/market/tickers?symbol={symbol}"
        return self._request("GET", endpoint)
    
    def get_order_book(self, symbol):
        endpoint = f"/api/v1/market/depth?symbol={symbol}"
        return self._request("GET", endpoint)
    
    def create_order(self, symbol, side, order_type, quantity, price=None):
        endpoint = "/api/v1/trade/order"
        data = {
            "symbol": symbol,
            "side": side.upper(),
            "type": order_type.upper(),
            "size": str(quantity),
        }
        if price is not None:
            data["price"] = str(price)
        return self._request("POST", endpoint, data=data, signed=True)
    
    def cancel_order(self, symbol, order_id):
        endpoint = "/api/v1/trade/order"
        params = {
            "symbol": symbol,
            "orderId": order_id
        }
        return self._request("DELETE", endpoint, params=params, signed=True)
    
    def get_order(self, symbol, order_id):
        endpoint = "/api/v1/trade/order"
        params = {
            "symbol": symbol,
            "orderId": order_id
        }
        return self._request("GET", endpoint, params=params, signed=True)
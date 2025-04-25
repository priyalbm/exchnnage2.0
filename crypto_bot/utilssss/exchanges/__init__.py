from .pionex import PionexExchange
# from .binance import BinanceExchange

EXCHANGE_CLASSES = {
    'PIONEX': PionexExchange,
    # 'BINANCE': BinanceExchange,
}

def get_exchange_client(exchange_code, api_key=None, api_secret=None):
    exchange_class = EXCHANGE_CLASSES.get(exchange_code.upper())
    if not exchange_class:
        raise ValueError(f"Unsupported exchange: {exchange_code}")
    return exchange_class(api_key, api_secret)
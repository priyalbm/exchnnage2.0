from rest_framework import serializers
from django.contrib.auth import get_user_model
User = get_user_model()

class CoinPairValidator:
    ALLOWED_PAIRS = {
        'BINANCE': [
            'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 
            'ADAUSDT', 'DOGEUSDT', 'XRPUSDT'
        ],
        'KUCOIN': [
            'BTC-USDT', 'ETH-USDT', 'XRP-USDT'
        ],
        'BYBIT': [
            'BTCUSDT', 'ETHUSDT', 'DOGEUSDT'
        ],
        'PIONEX': [
            'MNTC_USDT'
        ]
    }
    
    @classmethod
    def validate_coin_pair(cls, exchange, coin_pair):
        """
        Validate if the coin pair is supported for the given exchange
        """
        if exchange not in cls.ALLOWED_PAIRS:
            raise ValueError(f"Exchange {exchange} not supported")
        
        if coin_pair not in cls.ALLOWED_PAIRS[exchange]:
            raise ValueError(f"Coin pair {coin_pair} not supported for {exchange}")
        
        return True